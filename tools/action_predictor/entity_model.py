"""Trainable GRU/action/movement plus visible-entity attention; fixed targets."""
import copy
import torch
from torch import nn

class EntityMovementModel(nn.Module):
    def __init__(self,teacher,priority,dimension,use_entities):
        super().__init__();self.teacher=teacher.requires_grad_(False);self.priority=priority.requires_grad_(False)
        self.student=copy.deepcopy(teacher).requires_grad_(True);self.student.priority.requires_grad_(False)
        self.use_entities=bool(use_entities);state=torch.get_rng_state()
        self.entity_encoder=nn.Sequential(nn.Linear(dimension,64),nn.ReLU(),nn.Linear(64,64),nn.ReLU())
        self.entity_query=nn.Linear(128,64);self.entity_attention=nn.MultiheadAttention(64,4,dropout=0,batch_first=True)
        self.action_fusion=nn.Sequential(nn.Linear(233,128),nn.ReLU(),nn.Linear(128,128))
        self.movement_fusion=nn.Sequential(nn.Linear(233,128),nn.ReLU(),nn.Linear(128,128))
        for fusion in (self.action_fusion,self.movement_fusion):
            nn.init.zeros_(fusion[-1].weight);nn.init.zeros_(fusion[-1].bias)
        torch.set_rng_state(state)

    def train(self,mode=True):
        super().train(mode);self.teacher.eval();self.priority.eval();return self

    def forward(self,x,history,entities,entity_mask,priority_features,teacher_context=None):
        _,base=self.student(x,history)
        if not self.use_entities:entities=torch.zeros_like(entities)
        encoded=self.entity_encoder(entities)
        pool,_=self.entity_attention(self.entity_query(base)[:,None],encoded,encoded,key_padding_mask=~entity_mask,need_weights=False)
        combined=torch.cat((base,pool[:,0],priority_features),-1)
        action=base+self.action_fusion(combined);movement=base+self.movement_fusion(combined)
        if teacher_context is None:
            with torch.no_grad():_,teacher_context=self.teacher(x,history)
        return self.student.action(action),movement,teacher_context

    def parameter_logits(self,movement,teacher_context,grid,valid,family,rules):
        teacher=self.teacher.parameter_logits(teacher_context,grid,valid,family,rules)
        student=self.student.parameter_logits(movement,grid,valid,family,rules)
        selected=(family==8)|(family==3) # Bound retained label order: move/blocked.
        return torch.where(selected[:,None],student,teacher)
