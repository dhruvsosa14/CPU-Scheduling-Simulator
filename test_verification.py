"""
Verification script for Priority Scheduling and Multilevel Queue Scheduling.
Tests the scheduling engine logic on the Stage 1 benchmark dataset.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

@dataclass
class Process:
    pid: str
    arrival_time: int
    burst_time: int
    priority: int
    queue_type: str  # "System", "Interactive", "Background"
    remaining_time: int = 0
    start_time: int = -1
    completion_time: int = 0
    turnaround_time: int = 0
    waiting_time: int = 0
    response_time: int = -1

    def __post_init__(self):
        self.remaining_time = self.burst_time

@dataclass
class GanttBlock:
    pid: str
    start_time: int
    end_time: int
    is_idle: bool = False

def run_priority_scheduling(processes: List[Process]) -> Tuple[List[GanttBlock], List[Process], Dict[str, float]]:
    # Clone processes
    procs = [
        Process(
            pid=p.pid,
            arrival_time=p.arrival_time,
            burst_time=p.burst_time,
            priority=p.priority,
            queue_type=p.queue_type
        )
        for p in processes
    ]
    
    current_time = 0
    completed = 0
    n = len(procs)
    gantt: List[GanttBlock] = []
    
    while completed < n:
        # Find arrived and uncompleted processes
        available = [p for p in procs if p.arrival_time <= current_time and p.completion_time == 0]
        
        if not available:
            # CPU is idle until the next process arrives
            next_arrival = min(p.arrival_time for p in procs if p.completion_time == 0)
            gantt.append(GanttBlock(pid="IDLE", start_time=current_time, end_time=next_arrival, is_idle=True))
            current_time = next_arrival
            continue
            
        # Select highest priority (lowest numerical value), tie breaker: arrival time, then PID
        selected = min(available, key=lambda p: (p.priority, p.arrival_time, p.pid))
        
        selected.start_time = current_time
        selected.response_time = current_time - selected.arrival_time
        start = current_time
        current_time += selected.burst_time
        selected.completion_time = current_time
        selected.turnaround_time = selected.completion_time - selected.arrival_time
        selected.waiting_time = selected.turnaround_time - selected.burst_time
        completed += 1
        
        gantt.append(GanttBlock(pid=selected.pid, start_time=start, end_time=current_time, is_idle=False))
        
    total_time = current_time
    busy_time = sum(p.burst_time for p in procs)
    avg_wt = sum(p.waiting_time for p in procs) / n
    avg_tat = sum(p.turnaround_time for p in procs) / n
    avg_rt = sum(p.response_time for p in procs) / n
    cpu_util = (busy_time / total_time * 100) if total_time > 0 else 0
    throughput = n / total_time if total_time > 0 else 0
    
    metrics = {
        "avg_waiting_time": avg_wt,
        "avg_turnaround_time": avg_tat,
        "avg_response_time": avg_rt,
        "cpu_utilization": cpu_util,
        "throughput": throughput,
        "total_time": total_time
    }
    return gantt, procs, metrics

def run_mlq_scheduling(processes: List[Process], quantum: int = 2) -> Tuple[List[GanttBlock], List[Process], Dict[str, float]]:
    """
    Multilevel Queue Scheduling with 3 queues:
    Q1: System (Priority Scheduling - Priority 1 is highest)
    Q2: Interactive (Round Robin with time quantum)
    Q3: Background (FCFS)
    Preemptive priority between queues: Q1 > Q2 > Q3.
    """
    procs = [
        Process(
            pid=p.pid,
            arrival_time=p.arrival_time,
            burst_time=p.burst_time,
            priority=p.priority,
            queue_type=p.queue_type
        )
        for p in processes
    ]
    
    current_time = 0
    completed = 0
    n = len(procs)
    gantt: List[GanttBlock] = []
    
    # Q2 ready queue for Round Robin
    q2_ready: List[Process] = []
    # Track which processes have been added to q2_ready
    q2_enqueued = set()
    
    while completed < n:
        # Check newly arrived Q2 processes and enqueue
        for p in procs:
            if p.queue_type == "Interactive" and p.arrival_time <= current_time and p.pid not in q2_enqueued:
                q2_ready.append(p)
                q2_enqueued.add(p.pid)
                
        # 1. Check Q1: System processes (Priority scheduling among arrived)
        q1_available = [p for p in procs if p.queue_type == "System" and p.arrival_time <= current_time and p.remaining_time > 0]
        
        if q1_available:
            # Pick highest priority in Q1
            selected = min(q1_available, key=lambda p: (p.priority, p.arrival_time, p.pid))
            if selected.start_time == -1:
                selected.start_time = current_time
                selected.response_time = current_time - selected.arrival_time
                
            # System queue executes until completion or until higher priority Q1 arrives
            # Since Q1 processes arrive, let's execute 1 unit of time or entire burst if no new Q1 arrives
            # In standard non-preemptive within Q1:
            exec_time = selected.remaining_time
            selected.remaining_time = 0
            start = current_time
            current_time += exec_time
            selected.completion_time = current_time
            selected.turnaround_time = selected.completion_time - selected.arrival_time
            selected.waiting_time = selected.turnaround_time - selected.burst_time
            completed += 1
            gantt.append(GanttBlock(pid=selected.pid, start_time=start, end_time=current_time))
            continue
            
        # 2. Check Q2: Interactive processes (Round Robin)
        # Update Q2 ready queue with processes that arrived up to current_time
        for p in procs:
            if p.queue_type == "Interactive" and p.arrival_time <= current_time and p.pid not in q2_enqueued:
                q2_ready.append(p)
                q2_enqueued.add(p.pid)
                
        q2_active = [p for p in q2_ready if p.remaining_time > 0]
        if q2_active:
            selected = q2_ready.pop(0)
            while selected.remaining_time == 0:
                if not q2_ready:
                    selected = None
                    break
                selected = q2_ready.pop(0)
                
            if selected and selected.remaining_time > 0:
                if selected.start_time == -1:
                    selected.start_time = current_time
                    selected.response_time = current_time - selected.arrival_time
                    
                slice_time = min(quantum, selected.remaining_time)
                # Check if any Q1 process arrives during this slice
                # If Q1 arrives at t < current_time + slice_time, preempt
                q1_future_arrivals = [p.arrival_time for p in procs if p.queue_type == "System" and p.remaining_time > 0 and current_time < p.arrival_time < current_time + slice_time]
                if q1_future_arrivals:
                    actual_exec = min(q1_future_arrivals) - current_time
                else:
                    actual_exec = slice_time
                    
                start = current_time
                current_time += actual_exec
                selected.remaining_time -= actual_exec
                gantt.append(GanttBlock(pid=selected.pid, start_time=start, end_time=current_time))
                
                # Check newly arrived Q2 during this execution
                for p in procs:
                    if p.queue_type == "Interactive" and p.arrival_time <= current_time and p.pid not in q2_enqueued:
                        q2_ready.append(p)
                        q2_enqueued.add(p.pid)
                        
                if selected.remaining_time == 0:
                    selected.completion_time = current_time
                    selected.turnaround_time = selected.completion_time - selected.arrival_time
                    selected.waiting_time = selected.turnaround_time - selected.burst_time
                    completed += 1
                else:
                    q2_ready.append(selected)
                continue
                
        # 3. Check Q3: Background processes (FCFS)
        q3_available = [p for p in procs if p.queue_type == "Background" and p.arrival_time <= current_time and p.remaining_time > 0]
        if q3_available:
            selected = min(q3_available, key=lambda p: (p.arrival_time, p.pid))
            if selected.start_time == -1:
                selected.start_time = current_time
                selected.response_time = current_time - selected.arrival_time
                
            # Q3 runs until a higher priority process arrives or it completes
            # Next potential arrival in Q1 or Q2
            higher_arrivals = [
                p.arrival_time for p in procs 
                if (p.queue_type in ["System", "Interactive"]) and p.remaining_time > 0 and p.arrival_time > current_time
            ]
            
            if higher_arrivals:
                next_higher = min(higher_arrivals)
                if next_higher < current_time + selected.remaining_time:
                    exec_time = next_higher - current_time
                else:
                    exec_time = selected.remaining_time
            else:
                exec_time = selected.remaining_time
                
            start = current_time
            current_time += exec_time
            selected.remaining_time -= exec_time
            gantt.append(GanttBlock(pid=selected.pid, start_time=start, end_time=current_time))
            
            if selected.remaining_time == 0:
                selected.completion_time = current_time
                selected.turnaround_time = selected.completion_time - selected.arrival_time
                selected.waiting_time = selected.turnaround_time - selected.burst_time
                completed += 1
            continue
            
        # If no process ready in any queue, CPU is idle
        uncompleted_arrivals = [p.arrival_time for p in procs if p.remaining_time > 0 and p.arrival_time > current_time]
        if uncompleted_arrivals:
            next_arrival = min(uncompleted_arrivals)
            gantt.append(GanttBlock(pid="IDLE", start_time=current_time, end_time=next_arrival, is_idle=True))
            current_time = next_arrival
        else:
            break

    # Merge contiguous Gantt blocks of the same PID
    merged_gantt: List[GanttBlock] = []
    for b in gantt:
        if merged_gantt and merged_gantt[-1].pid == b.pid and merged_gantt[-1].is_idle == b.is_idle:
            merged_gantt[-1].end_time = b.end_time
        else:
            merged_gantt.append(GanttBlock(pid=b.pid, start_time=b.start_time, end_time=b.end_time, is_idle=b.is_idle))
            
    total_time = current_time
    busy_time = sum(p.burst_time for p in procs)
    avg_wt = sum(p.waiting_time for p in procs) / n
    avg_tat = sum(p.turnaround_time for p in procs) / n
    avg_rt = sum(p.response_time for p in procs) / n
    cpu_util = (busy_time / total_time * 100) if total_time > 0 else 0
    throughput = n / total_time if total_time > 0 else 0
    
    metrics = {
        "avg_waiting_time": avg_wt,
        "avg_turnaround_time": avg_tat,
        "avg_response_time": avg_rt,
        "cpu_utilization": cpu_util,
        "throughput": throughput,
        "total_time": total_time
    }
    return merged_gantt, procs, metrics

if __name__ == "__main__":
    benchmark = [
        Process("P1", 0, 5, 1, "System"),
        Process("P2", 1, 3, 2, "Interactive"),
        Process("P3", 2, 8, 4, "Background"),
        Process("P4", 3, 2, 1, "System"),
        Process("P5", 4, 4, 3, "Interactive"),
    ]
    
    print("=== PRIORITY SCHEDULING (Non-Preemptive) ===")
    g1, p1, m1 = run_priority_scheduling(benchmark)
    print("Gantt Chart:")
    for b in g1:
        print(f"  [{b.start_time} - {b.end_time}] : {b.pid}")
    print("\nProcess Table:")
    for p in sorted(p1, key=lambda x: x.pid):
        print(f"  {p.pid}: AT={p.arrival_time}, BT={p.burst_time}, Prio={p.priority}, CT={p.completion_time}, TAT={p.turnaround_time}, WT={p.waiting_time}, RT={p.response_time}")
    print("\nMetrics:", m1)
    
    print("\n=== MULTILEVEL QUEUE SCHEDULING (Quantum=2) ===")
    g2, p2, m2 = run_mlq_scheduling(benchmark, quantum=2)
    print("Gantt Chart:")
    for b in g2:
        print(f"  [{b.start_time} - {b.end_time}] : {b.pid}")
    print("\nProcess Table:")
    for p in sorted(p2, key=lambda x: x.pid):
        print(f"  {p.pid}: AT={p.arrival_time}, BT={p.burst_time}, Q={p.queue_type}, CT={p.completion_time}, TAT={p.turnaround_time}, WT={p.waiting_time}, RT={p.response_time}")
    print("\nMetrics:", m2)
