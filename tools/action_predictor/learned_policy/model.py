"""Learned objective state, achieved-goal prediction and goal-conditioned policy."""
import copy,math
import torch
from torch import nn
import torch.nn.functional as F

SPATIAL=(1,2,3,5,6,8,12,13,14)

class GoalPolicy(nn.Module):
    def __init__(self,teacher,persistent,goals=4):
        super().__init__();self.execution=copy.deepcopy(teacher).requires_grad_(True);self.execution.priority.requires_grad_(False);self.persistent=bool(persistent);self.goals=goals
        self.observation=nn.Sequential(nn.Linear(253,16),nn.Tanh());self.observation_history=nn.GRU(45,32,batch_first=True);self.history_projection=nn.Linear(32,128);nn.init.zeros_(self.history_projection.weight);nn.init.zeros_(self.history_projection.bias)
        self.objectives=nn.Parameter(torch.randn(goals,128)*.001);self.initial_offsets=nn.Parameter(torch.randn(goals,2)*.1);self.proposal=nn.Sequential(nn.Linear(146,64),nn.Tanh(),nn.Linear(64,goals))
        self.entity=nn.Sequential(nn.Linear(119,32),nn.Tanh(),nn.Linear(32,32));self.public=nn.Sequential(nn.Linear(8,32),nn.Tanh(),nn.Linear(32,32));self.entity_query=nn.Linear(132,32);self.global_entities=nn.Linear(32,128);self.objective_entities=nn.Linear(32,128)
        for layer in (self.global_entities,self.objective_entities):nn.init.zeros_(layer.weight);nn.init.zeros_(layer.bias)
        self.retention=nn.Linear(150,1);nn.init.zeros_(self.retention.weight);nn.init.constant_(self.retention.bias,math.log(.99/.01))
        self.goal_prediction=nn.Linear(128,4);nn.init.zeros_(self.goal_prediction.weight);nn.init.zeros_(self.goal_prediction.bias)
        with torch.no_grad():self.goal_prediction.bias[2:]=-1.6
        self.goal_condition=nn.Linear(5,128);nn.init.zeros_(self.goal_condition.weight);nn.init.zeros_(self.goal_condition.bias)
    def empty(self,n):return dict(belief=torch.full((n,self.goals),1/self.goals),world=torch.zeros((n,self.goals,2)),known=torch.zeros((n,self.goals),dtype=torch.bool),age=torch.zeros((n,self.goals)))
    def begin(self,x,history,observations,history_gaps,transition_gap,position,position_known,entities,entity_mask,public_tokens,public_mask,state):
        initial=transition_gap[:,2]>.5;use_past=(~initial)&self.persistent;old_known=state['known']&use_past[:,None];usable_old=old_known&position_known[:,None];old_relative=(state['world']-position[:,None])*usable_old[:,:,None];old_age=state['age']*use_past[:,None];memory=torch.cat((old_relative,torch.log1p(old_age)[:,:,None]/8,usable_old[:,:,None].float()),-1)
        _,base=self.execution(x,history);encoded=self.observation(observations)*history_gaps[:,:,1:2];_,h=self.observation_history(torch.cat((history[:,-16:],encoded,history_gaps),-1));entity_encoded=torch.cat((self.entity(entities),self.public(public_tokens)),1);entity_mask=torch.cat((entity_mask,public_mask),1);mean=(entity_encoded*entity_mask[:,:,None]).sum(1)/entity_mask.sum(1).clamp_min(1)[:,None];context=base+self.history_projection(h[-1])+self.global_entities(mean);inputs=torch.cat((context,transition_gap),-1);proposal=self.proposal(inputs).softmax(-1);roots=torch.expm1(transition_gap[:,0]*8);remembered=(memory*state['belief'][:,:,None]).sum(1)
        retain=torch.exp(F.logsigmoid(self.retention(torch.cat((inputs,remembered),-1))[:,0])*roots) if self.persistent else torch.zeros(len(x));retain=torch.where(initial,torch.zeros_like(retain),retain);prior=retain[:,None]*state['belief']+(1-retain[:,None])*proposal;logprior=prior.clamp_min(1e-30).log().log_softmax(-1)
        query=self.entity_query(torch.cat((context[:,None]+self.objectives[None],memory),-1));attention=(torch.bmm(query,entity_encoded.transpose(1,2))/math.sqrt(32)).masked_fill(~entity_mask[:,None],-1e4).softmax(-1);latent=context[:,None]+self.objectives[None]+self.objective_entities(torch.bmm(attention,entity_encoded));raw_goal=self.goal_prediction(latent);new_world=position[:,None]+raw_goal[:,:,:2]+self.initial_offsets[None];new_known=position_known[:,None].expand(-1,self.goals);blend=torch.where(old_known&new_known,retain[:,None],old_known.float());world=blend[:,:,None]*state['world']+(1-blend[:,:,None])*new_world;known=old_known|new_known;relative=(world-position[:,None])*position_known[:,None,None];logscale=raw_goal[:,:,2:].clamp(-4,2);usable=known&position_known[:,None];age=retain[:,None]*(old_age+roots[:,None])
        conditioned=latent+self.goal_condition(torch.cat((relative,logscale,usable[:,:,None].float()),-1));return dict(context=conditioned,logprior=logprior,world=world,known=known,age=age,logscale=logscale,retain=retain)
    def types(self,step):return self.execution.action(step['context']).log_softmax(-1)
    def spatial_log_probs(self,step,grid,valid,rules,family):
        n,k,_=step['context'].shape;contexts=step['context'].reshape(n*k,128);repeat=lambda t:t.repeat_interleave(k,0)
        return self.execution.parameter_logits(contexts,repeat(grid),repeat(valid),repeat(family),repeat(rules)).log_softmax(-1).reshape(n,k,291)
    def observed(self,step,grid,valid,rules,y,py,priority_parameter_nll):
        n=len(y);typ=self.types(step);component=typ[torch.arange(n),:,y].clone();spatial=torch.zeros(n,dtype=torch.bool)
        for code in SPATIAL:spatial|=y==code
        if spatial.any():
            sub={key:value[spatial] for key,value in step.items()};lp=self.spatial_log_probs(sub,grid[spatial],valid[spatial],rules[spatial],y[spatial]);component[spatial]+=lp[torch.arange(int(spatial.sum())),:,py[spatial]]
        component[y==9]-=priority_parameter_nll[y==9,None];mass=torch.logsumexp(step['logprior']+component,1);posterior=(step['logprior']+component).softmax(-1);return -mass,dict(belief=posterior,world=step['world'],known=step['known'],age=step['age'])
    def achieved_goal_loss(self,step,target,available):
        scale=step['logscale'].exp();normal=-.5*(((target[:,None]-step['world'])/scale)**2+2*step['logscale']+math.log(2*math.pi)).sum(-1);loss=-torch.logsumexp(step['logprior']+normal,1);return torch.where(available,loss,torch.zeros_like(loss))
    def decode(self,step,grid,valid,rules,priority_mode,priority_mode_logp):
        typ=self.types(step);type_marginal=torch.logsumexp(step['logprior'][:,:,None]+typ,1);n=len(typ);coordinates=torch.full((n,15),-1,dtype=torch.long);family_mode=type_marginal.clone();parameter_lp={}
        for family in SPATIAL:
            codes=torch.full((n,),family,dtype=torch.long);lp=self.spatial_log_probs(step,grid,valid,rules,codes);joint=torch.logsumexp(step['logprior'][:,:,None]+typ[:,:,family,None]+lp,1);parameter_lp[family]=joint-type_marginal[:,family,None];family_mode[:,family],coordinates[:,family]=joint.max(-1)
        family_mode[:,9]+=priority_mode_logp;prediction=family_mode.argmax(-1);row=torch.arange(n);return dict(prediction=prediction,coordinate=coordinates[row,prediction],priority=priority_mode,type_logp=type_marginal,parameter_logp=parameter_lp,goal_prior=step['logprior'].exp(),goal_world=step['world'],goal_known=step['known'],retention=step['retain'])
