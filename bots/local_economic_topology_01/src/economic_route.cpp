#include "economic_route.h"
#include <algorithm>
#include <cstdlib>
#include <tuple>
namespace lp::economic {
namespace {
int distance(Point a,Point b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
constexpr int directions[8][2]={{-1,-1},{0,-1},{1,-1},{-1,0},{1,0},{-1,1},{0,1},{1,1}};
}
Route::Attempt* Route::attempt(Key key,bool create) {
    for(auto& a:attempts)if(a.key==key)return &a;
    if(!create||attempts.size()>=capacity)return nullptr;
    attempts.push_back({key});return &attempts.back();
}
bool Route::visit(Attempt& a,unsigned cell,bool count_novel) {
    auto ordinal=unsigned(&a-attempts.data());
    for(auto v:visited)if(v.attempt==ordinal&&v.cell==cell)return true;
    if(visited.size()>=cells){a.exhausted=true;a.failure=RouteFailure::capacity;return false;}
    visited.push_back({std::uint16_t(ordinal),std::uint16_t(cell)});
    if(count_novel)a.novel=true;
    return true;
}
RouteResult Route::fail(RouteFailure reason) {
    if(auto* a=attempt(job.active?job.key:active,false)){a->exhausted=true;a->failure=reason;}
    cancel_job();return {reason==RouteFailure::capacity?Travel::capacity:Travel::exhausted,reason,{}};
}
RouteResult Route::start(Field field,Key key,const std::vector<Point>& contacts,bool repair) {
    auto* a=attempt(key);if(!a)return {Travel::capacity,RouteFailure::capacity,{}};
    if(a->exhausted)return {Travel::exhausted,a->failure,{}};
    if(job.active)return {Travel::planning,RouteFailure::none,{}};
    const auto n=std::int64_t(field.width)*field.height;
    if(!field.complete||field.width<=0||field.height<=0||n>cells||
        n!=std::int64_t(field.blocked.size())||n!=std::int64_t(field.covered.size())||
        n!=std::int64_t(field.distances.size())||field.origin.x<0||field.origin.y<0||
        field.origin.x>=field.width||field.origin.y>=field.height)
        return {Travel::capacity,RouteFailure::invalid_field,{}};
    const unsigned root=unsigned(field.origin.y*field.width+field.origin.x);
    if(field.blocked[root]||field.distances[root]!=0)return {Travel::blocked,RouteFailure::invalid_field,{}};
    const bool same=active==key&&!path.empty()&&width==field.width&&height==field.height;
    if(width&&(width!=field.width||height!=field.height))return {Travel::capacity,RouteFailure::invalid_field,{}};
    if(!same){path.clear();cursor=0;active=key;}
    width=field.width;height=field.height;
    Point contact;bool found=false;int suffix=-1;
    auto reachable=[&](Point p){return inside(p)&&!field.blocked[index(p)]&&field.distances[index(p)]!=65535;};
    if(repair&&same) {
        if(a->repairs>=8)return fail(RouteFailure::repair);
        ++a->repairs;
        const unsigned first=((cursor/4)+1)*4;
        unsigned previous=cursor;
        for(unsigned anchor=0;anchor<4;++anchor) {
            const unsigned at=std::min(first+anchor*4,unsigned(path.size()-1));
            if(at==previous)break;
            previous=at;
            const auto p=point(path[at]);
            if(reachable(p)){contact=p;suffix=int(at);found=true;break;}
        }
    }
    if(!found) {
        if(a->builds>=3)return fail(RouteFailure::replacement);
        ++a->builds;
        std::tuple<unsigned,int,int> best{65535,0,0};
        for(auto p:contacts)if(reachable(p)) {
            auto rank=std::tuple{unsigned(field.distances[index(p)]),p.y,p.x};
            if(!found||rank<best){best=rank;contact=p;found=true;}
        }
    }
    if(!found)return {Travel::blocked,RouteFailure::no_contact,{}};
    job.field=std::move(field);job.key=key;job.target=contact;job.suffix=suffix;
    if(suffix>=0)job.suffix_index.reset(new std::uint16_t[std::size_t(n)]);
    job.active=true;job.conditional=job.field.conditional;scratch.clear();published.clear();
    if(!visit(*a,index(job.field.origin),false))return fail(RouteFailure::capacity);
    return {Travel::planning,RouteFailure::none,{}};
}
RouteResult Route::continue_plan(action::Epoch epoch,Point origin,unsigned& writes) {
    if(!job.active)return {Travel::blocked,RouteFailure::no_contact,{}};
    auto* a=attempt(job.key,false);if(!a)return fail(RouteFailure::capacity);
    if(epoch.actor!=job.field.epoch.actor||epoch.life!=job.field.epoch.life||origin!=job.field.origin) {
        cancel_job();return {Travel::stale,RouteFailure::none,{}};
    }
    job.conditional|=epoch!=job.field.epoch;
    if(job.last_round!=epoch.round) {
        job.last_round=epoch.round;
        if(++job.turns>8)return fail(RouteFailure::planning);
        if(a->planning_round!=epoch.round) {
            a->planning_round=epoch.round;
            if(++a->planning>32)return fail(RouteFailure::planning);
        }
    }
    // Old paths remain immutable until COMPLETE extraction and suffix splice.
    while(writes<scalar_batch&&job.active) {
        if(job.phase==0) {
            if(job.suffix_index) {
                if(job.initialize_cursor<unsigned(width*height)) {
                    job.suffix_index[job.initialize_cursor++]=65535;++writes;continue;
                }
                if(job.write_cursor<path.size()) {
                    job.suffix_index[path[job.write_cursor]]=std::uint16_t(job.write_cursor);
                    ++job.write_cursor;++writes;continue;
                }
            }
            job.write_cursor=0;job.phase=1;
        }
        if(job.phase==1) {
            Point p=scratch.empty()?job.target:point(scratch.back());
            if(scratch.empty()){scratch.push_back(std::uint16_t(index(p)));++writes;}
            if(p==job.field.origin){job.phase=2;continue;}
            if(writes>=scalar_batch)break;
            const auto d=job.field.distances[index(p)];bool found=false;
            for(auto direction:directions) {
                Point q{p.x+direction[0],p.y+direction[1]};
                if(inside(q)&&!job.field.blocked[index(q)]&&d>0&&
                    job.field.distances[index(q)]==d-1) {
                    scratch.push_back(std::uint16_t(index(q)));++writes;found=true;break;
                }
            }
            if(!found||scratch.size()>std::size_t(width*height))return fail(RouteFailure::invalid_field);
            continue;
        }
        if(job.phase==2) {
            if(job.write_cursor<scratch.size()) {
                auto cell=scratch[scratch.size()-1-job.write_cursor++];
                if(!published.empty()&&distance(point(published.back()),point(cell))!=1)return fail(RouteFailure::invalid_field);
                published.push_back(cell);++writes;
                job.conditional|=!job.field.covered[cell];
                if(job.suffix_index&&job.suffix_index[cell]!=65535&&
                    job.suffix_index[cell]>=unsigned(job.suffix)) {
                    // First exact prefix/suffix meeting. Keep the unchanged
                    // later suffix and omit the resulting overlap loop.
                    job.phase=3;job.write_cursor=unsigned(job.suffix_index[cell])+1;
                }
                continue;
            }
            job.phase=3;job.write_cursor=job.suffix<0?unsigned(path.size()):unsigned(job.suffix)+1;
        }
        if(job.phase==3&&job.write_cursor<path.size()) {
            auto cell=path[job.write_cursor++];
            if(!published.empty()&&distance(point(published.back()),point(cell))!=1)return fail(RouteFailure::invalid_field);
            if(published.size()>=std::size_t(width*height))return fail(RouteFailure::capacity);
            published.push_back(cell);
            ++writes;continue;
        }
        if(published.empty()||point(published.front())!=origin)return fail(RouteFailure::invalid_field);
        auto target=job.suffix<0?job.target:point(path.back());
        if(point(published.back())!=target)return fail(RouteFailure::invalid_field);
        const bool conditional=job.conditional;
        path=std::move(published);cursor=0;active=job.key;conditional_=conditional;cancel_job();
        auto result=next(active,origin);result.conditional=conditional;return result;
    }
    return {Travel::planning,RouteFailure::none,{}};
}
RouteResult Route::next(Key key,Point origin)const {
    if(active!=key||path.empty())return {Travel::blocked,RouteFailure::no_contact,{}};
    if(cursor>=path.size()||point(path[cursor])!=origin)return {Travel::blocked,RouteFailure::none,{}};
    if(cursor+1==path.size())return {Travel::at_goal,RouteFailure::none,origin,conditional_};
    return {Travel::ready,RouteFailure::none,point(path[cursor+1]),conditional_};
}
bool Route::motion(std::uint64_t event,Key key,Point from,Point to,bool accepted,bool coherent,bool charge) {
    if(!event||event<=last_motion_event)return false;
    last_motion_event=event;
    if(accepted)conditional_=true;
    auto* a=attempt(key);if(!a)return false;
    if(!accepted) {
        if(!charge)return false;
        for(auto& edge:failed)if(edge.key==key&&edge.from==from&&edge.to==to) {
            if(edge.event==event)return false;
            edge.event=event;if(++edge.failures>=2){a->exhausted=true;a->failure=RouteFailure::contact;}return false;
        }
        if(failed.size()>=capacity){a->exhausted=true;a->failure=RouteFailure::capacity;return false;}
        failed.push_back({key,from,to,1,event});return false;
    }
    ++a->motions;if(a->motions>=512){a->exhausted=true;a->failure=RouteFailure::motions;}
    if(!coherent||active!=key||path.empty()||point(path[cursor])!=from)return false;
    // Only the next one/two edges, and never beyond the next four-edge anchor.
    const unsigned anchor=std::min(((cursor/4)+1)*4,unsigned(path.size()-1));
    for(unsigned at=cursor+1;at<=std::min(cursor+2,anchor);++at)if(point(path[at])==to) {
        cursor=at;
        if(!visit(*a,index(to),true))return false;
        cancel_job();return true;
    }
    cancel_job();return false;
}
RouteResult Route::finish_execution(Key key,int round,bool eligible,bool work) {
    auto* a=attempt(key);if(!a)return {Travel::capacity,RouteFailure::capacity,{}};
    if(eligible&&a->execution_round!=round) {
        a->execution_round=round;
        if(a->novel||work)a->stall=0;
        else if(++a->stall>=8){a->exhausted=true;a->failure=RouteFailure::stalled;}
    }
    a->novel=false;
    return {a->exhausted?Travel::exhausted:Travel::ready,
        a->exhausted?a->failure:RouteFailure::none,{}};
}
bool Route::reopen(Key key,Reason reason,std::uint64_t fact) {
    if(!fact||reason==Reason::none)return false;
    auto* a=attempt(key,false);if(!a||!a->exhausted||a->reopening_fact==fact)return false;
    // Caller supplies addressed positive evidence, never a timer/revision.
    *a=Attempt{key};a->reopening_fact=fact;
    const auto ordinal=unsigned(a-attempts.data());
    visited.erase(std::remove_if(visited.begin(),visited.end(),[&](auto v){return v.attempt==ordinal;}),visited.end());
    failed.erase(std::remove_if(failed.begin(),failed.end(),[&](const auto& e){return e.key==key;}),failed.end());
    return true;
}
}
