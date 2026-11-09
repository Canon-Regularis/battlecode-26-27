"""Minimum-duration switching prototypes learned without objective names.

Hard EM alternates exact sequence assignment with weighted centroid updates.
This is a small semi-Markov clustering model, not a CompILE reproduction.
"""
import numpy as np


def decode(costs,penalty=2.,minimum=2):
    costs=np.asarray(costs,dtype=np.float64);t,k=costs.shape
    if t<minimum or not np.isfinite(costs).all():raise ValueError('Invalid sequence costs')
    dp=np.full((k,minimum),np.inf);dp[:,0]=costs[0]
    back=np.full((t,k,minimum,2),-1,np.int32)
    for i in range(1,t):
        nxt=np.full_like(dp,np.inf)
        for state in range(k):
            for age in range(minimum):
                a=min(age+1,minimum-1);v=dp[state,age]+costs[i,state]
                if v<nxt[state,a]:nxt[state,a]=v;back[i,state,a]=(state,age)
            alternatives=dp[:,minimum-1]+penalty;alternatives=alternatives.copy();alternatives[state]=np.inf
            prior=int(alternatives.argmin());v=alternatives[prior]+costs[i,state]
            if v<nxt[state,0]:nxt[state,0]=v;back[i,state,0]=(prior,minimum-1)
        dp=nxt
    state=int(dp[:,minimum-1].argmin());age=minimum-1;value=float(dp[state,age]);labels=np.empty(t,np.int32)
    for i in range(t-1,-1,-1):
        labels[i]=state
        if i:state,age=back[i,state,age]
    return labels,value


def ranges(labels):
    start=0
    for i in range(1,len(labels)+1):
        if i==len(labels) or labels[i]!=labels[start]:
            yield start,i,int(labels[start]);start=i


def transform(values,mask,mean,scale):
    return np.where(mask,(values-mean)/scale,0.)


def emission(values,mask,centers):
    weights=mask/np.maximum(mask.sum(-1,keepdims=True),1)
    return (((values[:,None,:]-centers[None,:,:])**2)*weights[:,None,:]).sum(-1)


def fit(sequences,k=8,iterations=12,penalty=2.,minimum=2,seed=43002):
    y=np.concatenate([s[0] for s in sequences]);m=np.concatenate([s[1] for s in sequences]).astype(float)
    mean=(y*m).sum(0)/m.sum(0).clip(1)
    scale=np.sqrt((((y-mean)**2)*m).sum(0)/m.sum(0).clip(1)).clip(.1)
    normalized=[(transform(a,b,mean,scale),b.astype(float)) for a,b in sequences]
    full=np.concatenate([a for a,b in normalized]);weights=m/m.sum(-1,keepdims=True).clip(1)
    rng=np.random.default_rng(seed);chosen=[int(rng.integers(len(full)))];dist=np.full(len(full),np.inf)
    for _ in range(k-1):
        dist=np.minimum(dist,((full-full[chosen[-1]])**2*weights).sum(-1))
        chosen.append(int(rng.choice(len(full),p=dist/dist.sum())) if dist.sum()>0 else len(chosen)%len(full))
    centers=full[chosen].copy();trace=[]
    for iteration in range(iterations):
        assigned=[];objective=0.
        for a,b in normalized:
            labels,value=decode(emission(a,b,centers),penalty,minimum);assigned.append(labels);objective+=value
        labels=np.concatenate(assigned);new=centers.copy()
        for code in range(k):
            take=labels==code;den=weights[take].sum(0);num=(full[take]*weights[take]).sum(0)
            new[code]=np.where(den>0,num/den.clip(1e-12),centers[code])
        trace.append(dict(iteration=iteration+1,objective=objective,occupancy=np.bincount(labels,minlength=k).tolist()))
        centers=new
    return dict(mean=mean.tolist(),scale=scale.tolist(),centers=centers.tolist(),penalty=penalty,minimum=minimum,trace=trace)


def assign(values,mask,fitted):
    z=transform(np.asarray(values),np.asarray(mask),np.asarray(fitted['mean']),np.asarray(fitted['scale']))
    return decode(emission(z,np.asarray(mask),np.asarray(fitted['centers'])),fitted['penalty'],fitted['minimum'])[0]
