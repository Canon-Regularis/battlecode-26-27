#pragma once
#include "economic_owner.h"
#include <memory>
#include <vector>
namespace lp::economic {
enum class Travel { ready, at_goal, planning, blocked, exhausted, capacity, stale };
enum class RouteFailure { none, no_contact, invalid_field, replacement, repair,
    contact, motions, stalled, planning, capacity };
struct Field {
    action::Epoch epoch;
    Point origin;
    int width=0,height=0;
    std::uint64_t graph=0;
    bool complete=false;
    std::vector<std::uint8_t> blocked,covered;
    std::vector<std::uint16_t> distances;
    bool conditional=false;
};
struct RouteResult {
    Travel status=Travel::blocked;
    RouteFailure reason=RouteFailure::none;
    Point next;
    bool conditional=false;
};
// Owns the entire accepted route and its suffix, plus durable finite attempts.
// Field production is native SDK work; extraction/splicing uses owned scalars.
class Route {
    struct Attempt {
        Key key;
        unsigned builds=0,repairs=0,motions=0,stall=0,planning=0;
        int execution_round=-1,planning_round=-1;
        bool exhausted=false,novel=false;
        RouteFailure failure=RouteFailure::none;
        std::uint64_t reopening_fact=0;
    };
    struct FailedEdge {Key key;Point from,to;unsigned failures=0;std::uint64_t event=0;};
    std::vector<Attempt> attempts;
    std::vector<FailedEdge> failed;
    std::vector<std::uint16_t> path,scratch,published;
    struct Visit {std::uint16_t attempt,cell;};
    std::vector<Visit> visited;
    Key active;
    unsigned cursor=0;
    bool conditional_=false;
    int width=0,height=0;
    struct Job {
        Field field;
        Key key;
        Point target;
        int suffix=-1,last_round=-1;
        unsigned phase=0,write_cursor=0,turns=0;
        std::unique_ptr<std::uint16_t[]> suffix_index;
        unsigned initialize_cursor=0;
        bool active=false,conditional=false;
    } job;
    std::uint64_t last_motion_event=0;
    Attempt* attempt(Key,bool create=true);
    bool visit(Attempt&,unsigned cell,bool count_novel);
    RouteResult fail(RouteFailure);
    Point point(unsigned cell)const{return {int(cell)%width,int(cell)/width};}
    unsigned index(Point p)const{return unsigned(p.y*width+p.x);}
    bool inside(Point p)const{return p.x>=0&&p.y>=0&&p.x<width&&p.y<height;}
public:
    static constexpr unsigned cells=16384,capacity=512,scalar_batch=4096;
    const std::vector<std::uint16_t>& accepted_path()const{return path;}
    unsigned position()const{return cursor;}
    bool planning()const{return job.active;}
    // All contacts and the field refer to ONE frozen graph and actual origin.
    // repair uses the first reachable of the next four four-edge anchors.
    RouteResult start(Field,Key,const std::vector<Point>& contacts,bool repair);
    RouteResult continue_plan(action::Epoch,Point,unsigned& shared_scalar_writes);
    RouteResult next(Key,Point)const;
    bool motion(std::uint64_t event,Key,Point from,Point to,bool accepted,
                bool coherent,bool charged_failed_contact);
    RouteResult finish_execution(Key,int round,bool eligible,bool economic_work);
    bool reopen(Key,Reason,std::uint64_t positive_fact);
    void cancel_job(){job={};scratch.clear();published.clear();}
};
}
