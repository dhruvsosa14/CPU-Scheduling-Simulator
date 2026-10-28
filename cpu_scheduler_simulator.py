"""
================================================================================
SHAH & ANCHOR KUTCHHI ENGINEERING COLLEGE
Department of Computer Engineering - Academic Year 2025-2026 / 2026-2027
Subject: Operating System (OS)
SLA Stage 2: Working Implementation & GUI Prototype
Project Title: Multilevel Queue (MLQ) Scheduling & Priority Queue Scheduling
Students: Rajvi Shah (Roll 52, PRN 125BTCM1040)
          Dhruv Sosa (Roll 54, PRN 125BTCM1004)
Guide:    Prof. Deepshikha Chaturvedi
================================================================================
File: cpu_scheduler_simulator.py
Description:
    A modular, fully documented CPU scheduling simulation system featuring:
    1. Non-Preemptive Priority Scheduling (Priority 1 = Highest)
    2. Multilevel Queue (MLQ) Scheduling (3 Queues: System, Interactive, Background)
    3. Interactive Tkinter GUI with custom Gantt Chart, Performance Metrics,
       Input Validation, Edge Case Handling, and Side-by-Side Algorithm Comparison.
================================================================================
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox

# ==============================================================================
# 1. CORE DATA STRUCTURES
# ==============================================================================

@dataclass
class Process:
    """
    Data model representing a single schedulable Operating System process.
    """
    pid: str
    arrival_time: int
    burst_time: int
    priority: int  # 1 = Highest priority, higher numbers indicate lower priority
    queue_type: str  # 'System' (Q1), 'Interactive' (Q2), or 'Background' (Q3)
    
    # Dynamic execution state attributes
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
    """
    Data model representing an execution block on the CPU timeline.
    """
    pid: str
    start_time: int
    end_time: int
    is_idle: bool = False
    queue_type: str = "System"


# ==============================================================================
# 2. SCHEDULING ENGINES (MODULAR IMPLEMENTATION)
# ==============================================================================

class PriorityScheduler:
    """
    Implements Non-Preemptive Priority CPU Scheduling.
    
    Working Principle:
    - Arrived processes are checked at each dispatch point.
    - The process with the highest priority (lowest numeric priority value) is
      selected and allowed to run to completion (non-preemptive).
    - FCFS (Arrival Time, then PID) serves as the deterministic tie-breaker.
    - CPU idle intervals are dynamically detected and recorded.
    """
    
    @staticmethod
    def schedule(processes: List[Process]) -> Tuple[List[GanttBlock], List[Process], Dict[str, float]]:
        # Create isolated copies to ensure immutability of original inputs
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
            # Filter processes that have arrived and not yet completed
            arrived = [p for p in procs if p.arrival_time <= current_time and p.completion_time == 0]
            
            if not arrived:
                # Boundary case: CPU is Idle
                next_arrival = min(p.arrival_time for p in procs if p.completion_time == 0)
                gantt.append(GanttBlock(
                    pid="IDLE",
                    start_time=current_time,
                    end_time=next_arrival,
                    is_idle=True,
                    queue_type="None"
                ))
                current_time = next_arrival
                continue
            
            # Select process with highest priority (min value), tie break: arrival time, then PID
            selected = min(arrived, key=lambda p: (p.priority, p.arrival_time, p.pid))
            
            selected.start_time = current_time
            selected.response_time = current_time - selected.arrival_time
            
            start_block = current_time
            current_time += selected.burst_time
            
            selected.completion_time = current_time
            selected.turnaround_time = selected.completion_time - selected.arrival_time
            selected.waiting_time = selected.turnaround_time - selected.burst_time
            completed += 1
            
            gantt.append(GanttBlock(
                pid=selected.pid,
                start_time=start_block,
                end_time=current_time,
                is_idle=False,
                queue_type=selected.queue_type
            ))
            
        metrics = MetricsEngine.calculate(procs, gantt, current_time)
        return gantt, procs, metrics


class MultilevelQueueScheduler:
    """
    Implements Multilevel Queue (MLQ) CPU Scheduling with 3 Priority Queues:
    
    - Queue 1 (System Processes): Highest priority queue; scheduled via Priority Scheduling.
    - Queue 2 (Interactive Processes): Medium priority queue; scheduled via Round Robin (Time Quantum).
    - Queue 3 (Background Processes): Lowest priority queue; scheduled via First-Come, First-Served (FCFS).
    
    Preemption across queues:
    - Fixed priority scheduling between queues: Q1 > Q2 > Q3.
    - Processes in Q2 run only when Q1 is empty. If a Q1 process arrives while Q2 runs,
      Q2 is preempted at the arrival boundary.
    - Processes in Q3 run only when both Q1 and Q2 are empty.
    """
    
    @staticmethod
    def schedule(processes: List[Process], quantum: int = 2) -> Tuple[List[GanttBlock], List[Process], Dict[str, float]]:
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
        raw_gantt: List[GanttBlock] = []
        
        # Internal ready queue for Round Robin (Queue 2)
        q2_ready: List[Process] = []
        q2_enqueued_set = set()
        
        while completed < n:
            # Enqueue newly arrived interactive processes into Q2 ready FIFO
            for p in procs:
                if p.queue_type == "Interactive" and p.arrival_time <= current_time and p.pid not in q2_enqueued_set:
                    q2_ready.append(p)
                    q2_enqueued_set.add(p.pid)
            
            # ------------------------------------------------------------------
            # LEVEL 1: Check Queue 1 (System Processes) - Priority Scheduling
            # ------------------------------------------------------------------
            q1_available = [
                p for p in procs 
                if p.queue_type == "System" and p.arrival_time <= current_time and p.remaining_time > 0
            ]
            
            if q1_available:
                # Highest priority in Q1
                selected = min(q1_available, key=lambda p: (p.priority, p.arrival_time, p.pid))
                if selected.start_time == -1:
                    selected.start_time = current_time
                    selected.response_time = current_time - selected.arrival_time
                    
                exec_duration = selected.remaining_time
                selected.remaining_time = 0
                start_block = current_time
                current_time += exec_duration
                
                selected.completion_time = current_time
                selected.turnaround_time = selected.completion_time - selected.arrival_time
                selected.waiting_time = selected.turnaround_time - selected.burst_time
                completed += 1
                
                raw_gantt.append(GanttBlock(
                    pid=selected.pid,
                    start_time=start_block,
                    end_time=current_time,
                    queue_type="System"
                ))
                continue
            
            # ------------------------------------------------------------------
            # LEVEL 2: Check Queue 2 (Interactive Processes) - Round Robin
            # ------------------------------------------------------------------
            # Refresh Q2 ready queue with processes that arrived up to current_time
            for p in procs:
                if p.queue_type == "Interactive" and p.arrival_time <= current_time and p.pid not in q2_enqueued_set:
                    q2_ready.append(p)
                    q2_enqueued_set.add(p.pid)
            
            # Find next valid process in Q2 FIFO
            selected_q2 = None
            while q2_ready:
                candidate = q2_ready.pop(0)
                if candidate.remaining_time > 0:
                    selected_q2 = candidate
                    break
            
            if selected_q2:
                if selected_q2.start_time == -1:
                    selected_q2.start_time = current_time
                    selected_q2.response_time = current_time - selected_q2.arrival_time
                
                intended_slice = min(quantum, selected_q2.remaining_time)
                
                # Check if higher priority Q1 process arrives during this quantum slice
                q1_future = [
                    p.arrival_time for p in procs 
                    if p.queue_type == "System" and p.remaining_time > 0 and current_time < p.arrival_time < current_time + intended_slice
                ]
                
                actual_exec = min(q1_future) - current_time if q1_future else intended_slice
                
                start_block = current_time
                current_time += actual_exec
                selected_q2.remaining_time -= actual_exec
                
                raw_gantt.append(GanttBlock(
                    pid=selected_q2.pid,
                    start_time=start_block,
                    end_time=current_time,
                    queue_type="Interactive"
                ))
                
                # Add newly arrived Q2 processes during execution before requeueing
                for p in procs:
                    if p.queue_type == "Interactive" and p.arrival_time <= current_time and p.pid not in q2_enqueued_set:
                        q2_ready.append(p)
                        q2_enqueued_set.add(p.pid)
                
                if selected_q2.remaining_time == 0:
                    selected_q2.completion_time = current_time
                    selected_q2.turnaround_time = selected_q2.completion_time - selected_q2.arrival_time
                    selected_q2.waiting_time = selected_q2.turnaround_time - selected_q2.burst_time
                    completed += 1
                else:
                    q2_ready.append(selected_q2)
                continue
            
            # ------------------------------------------------------------------
            # LEVEL 3: Check Queue 3 (Background Processes) - FCFS
            # ------------------------------------------------------------------
            q3_available = [
                p for p in procs 
                if p.queue_type == "Background" and p.arrival_time <= current_time and p.remaining_time > 0
            ]
            
            if q3_available:
                selected_q3 = min(q3_available, key=lambda p: (p.arrival_time, p.pid))
                if selected_q3.start_time == -1:
                    selected_q3.start_time = current_time
                    selected_q3.response_time = current_time - selected_q3.arrival_time
                
                # Check if higher priority Q1 or Q2 process arrives while Q3 executes
                higher_arrivals = [
                    p.arrival_time for p in procs 
                    if (p.queue_type in ["System", "Interactive"]) and p.remaining_time > 0 and p.arrival_time > current_time
                ]
                
                if higher_arrivals:
                    next_preemption = min(higher_arrivals)
                    exec_duration = min(selected_q3.remaining_time, next_preemption - current_time)
                else:
                    exec_duration = selected_q3.remaining_time
                
                start_block = current_time
                current_time += exec_duration
                selected_q3.remaining_time -= exec_duration
                
                raw_gantt.append(GanttBlock(
                    pid=selected_q3.pid,
                    start_time=start_block,
                    end_time=current_time,
                    queue_type="Background"
                ))
                
                if selected_q3.remaining_time == 0:
                    selected_q3.completion_time = current_time
                    selected_q3.turnaround_time = selected_q3.completion_time - selected_q3.arrival_time
                    selected_q3.waiting_time = selected_q3.turnaround_time - selected_q3.burst_time
                    completed += 1
                continue
            
            # ------------------------------------------------------------------
            # IDLE STATE: When no queue has ready processes
            # ------------------------------------------------------------------
            future_arrivals = [
                p.arrival_time for p in procs 
                if p.remaining_time > 0 and p.arrival_time > current_time
            ]
            
            if future_arrivals:
                next_arrival = min(future_arrivals)
                raw_gantt.append(GanttBlock(
                    pid="IDLE",
                    start_time=current_time,
                    end_time=next_arrival,
                    is_idle=True,
                    queue_type="None"
                ))
                current_time = next_arrival
            else:
                break
        
        # Merge consecutive timeline blocks of identical processes
        merged_gantt: List[GanttBlock] = []
        for block in raw_gantt:
            if merged_gantt and merged_gantt[-1].pid == block.pid and merged_gantt[-1].is_idle == block.is_idle:
                merged_gantt[-1].end_time = block.end_time
            else:
                merged_gantt.append(GanttBlock(
                    pid=block.pid,
                    start_time=block.start_time,
                    end_time=block.end_time,
                    is_idle=block.is_idle,
                    queue_type=block.queue_type
                ))
                
        metrics = MetricsEngine.calculate(procs, merged_gantt, current_time)
        return merged_gantt, procs, metrics


# ==============================================================================
# 3. METRICS ENGINE
# ==============================================================================

class MetricsEngine:
    """
    Computes statistical and performance parameters:
    - Completion Time (CT)
    - Turnaround Time (TAT = CT - AT)
    - Waiting Time (WT = TAT - BT)
    - Response Time (RT = First Start Time - AT)
    - CPU Utilization (%) = (Busy Time / Total Makespan) * 100
    - Throughput = Completed Processes / Total Time
    """
    
    @staticmethod
    def calculate(procs: List[Process], gantt: List[GanttBlock], total_time: int) -> Dict[str, float]:
        n = len(procs)
        if n == 0 or total_time == 0:
            return {
                "avg_waiting_time": 0.0,
                "avg_turnaround_time": 0.0,
                "avg_response_time": 0.0,
                "cpu_utilization": 0.0,
                "throughput": 0.0,
                "total_time": 0
            }
            
        busy_time = sum(b.end_time - b.start_time for b in gantt if not b.is_idle)
        avg_wt = sum(p.waiting_time for p in procs) / n
        avg_tat = sum(p.turnaround_time for p in procs) / n
        avg_rt = sum(p.response_time for p in procs) / n
        cpu_util = (busy_time / total_time * 100.0) if total_time > 0 else 0.0
        throughput = n / total_time if total_time > 0 else 0.0
        
        return {
            "avg_waiting_time": round(avg_wt, 2),
            "avg_turnaround_time": round(avg_tat, 2),
            "avg_response_time": round(avg_rt, 2),
            "cpu_utilization": round(cpu_util, 2),
            "throughput": round(throughput, 4),
            "total_time": total_time
        }


# ==============================================================================
# 4. GANTT CHART VISUAL CANVAS
# ==============================================================================

class GanttCanvas(tk.Canvas):
    """
    Custom Canvas component dedicated to rendering visual Gantt charts
    with accurate timeline scaling, distinct queue color palettes, process labels,
    idle states, and time indicators.
    """
    
    PALETTE = {
        "System": "#3B82F6",       # Vibrant Blue
        "Interactive": "#10B981",  # Fresh Emerald Green
        "Background": "#F59E0B",   # Warm Amber
        "IDLE": "#94A3B8",         # Neutral Gray
        "Border": "#1E293B",       # Slate Border
        "Text": "#FFFFFF"          # White
    }
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="#F8FAFC", highlightthickness=1, highlightbackground="#CBD5E1", **kwargs)
        
    def draw_gantt(self, gantt_blocks: List[GanttBlock]):
        self.delete("all")
        if not gantt_blocks:
            self.create_text(
                self.winfo_width() / 2 or 300, 50,
                text="No simulation data available. Click 'Run Simulation' to visualize execution.",
                fill="#64748B", font=("Segoe UI", 11, "italic")
            )
            return

        total_time = gantt_blocks[-1].end_time
        if total_time == 0:
            return
            
        width = max(self.winfo_width(), 700)
        margin_left = 50
        margin_right = 50
        chart_width = width - margin_left - margin_right
        y_top = 40
        y_bottom = 90
        
        # Draw legend at top
        legend_items = [
            ("Q1: System", self.PALETTE["System"]),
            ("Q2: Interactive", self.PALETTE["Interactive"]),
            ("Q3: Background", self.PALETTE["Background"]),
            ("Idle CPU", self.PALETTE["IDLE"])
        ]
        
        lx = margin_left
        for label, color in legend_items:
            self.create_rectangle(lx, 10, lx + 16, 24, fill=color, outline="#334155")
            self.create_text(lx + 24, 17, text=label, anchor="w", font=("Segoe UI", 9, "bold"), fill="#334155")
            lx += 140

        # Draw timeline start tick mark
        self.create_line(margin_left, y_bottom, margin_left, y_bottom + 8, fill="#0F172A", width=2)
        self.create_text(margin_left, y_bottom + 18, text="0", font=("Segoe UI", 9, "bold"), fill="#0F172A")
        
        for block in gantt_blocks:
            x_start = margin_left + (block.start_time / total_time) * chart_width
            x_end = margin_left + (block.end_time / total_time) * chart_width
            
            fill_color = self.PALETTE["IDLE"] if block.is_idle else self.PALETTE.get(block.queue_type, "#6366F1")
            
            # Draw Process Bar
            self.create_rectangle(
                x_start, y_top, x_end, y_bottom,
                fill=fill_color, outline="#1E293B", width=1.5
            )
            
            # Process Name Label
            block_center_x = (x_start + x_end) / 2
            label_text = f"{block.pid}" if not block.is_idle else "IDLE"
            duration = block.end_time - block.start_time
            
            # Only display duration inside bar if width is sufficient
            if (x_end - x_start) > 35:
                self.create_text(
                    block_center_x, (y_top + y_bottom) / 2,
                    text=f"{label_text}\n({duration})",
                    font=("Segoe UI", 9, "bold"),
                    fill="#FFFFFF" if not block.is_idle else "#0F172A",
                    justify="center"
                )
            else:
                self.create_text(
                    block_center_x, (y_top + y_bottom) / 2,
                    text=label_text,
                    font=("Segoe UI", 8, "bold"),
                    fill="#FFFFFF" if not block.is_idle else "#0F172A"
                )
                
            # Tick mark and timestamp at end of block
            self.create_line(x_end, y_bottom, x_end, y_bottom + 8, fill="#0F172A", width=2)
            self.create_text(x_end, y_bottom + 18, text=str(block.end_time), font=("Segoe UI", 9, "bold"), fill="#0F172A")


# ==============================================================================
# 5. GRAPHICAL USER INTERFACE (GUI) APPLICATION
# ==============================================================================

class CPUSchedulingSimulatorGUI:
    """
    Master GUI Application incorporating:
    - Input handling with rigorous validation
    - Algorithm selection (Priority, MLQ, Comparative)
    - Execution controllers
    - Visual Gantt chart inspection
    - Result tables and side-by-side performance comparison
    """
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CPU Scheduling Simulator | Priority & Multilevel Queue (MLQ)")
        self.root.geometry("1180x820")
        self.root.minsize(1050, 720)
        
        self.processes: List[Process] = []
        self._setup_styles()
        self._build_layout()
        self.load_benchmark_dataset()
        
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Primary aesthetic palette
        style.configure(".", font=("Segoe UI", 10), background="#F1F5F9", foreground="#0F172A")
        style.configure("Header.TFrame", background="#1E293B")
        style.configure("Card.TFrame", background="#FFFFFF", relief="flat")
        
        # Buttons
        style.configure("Primary.TButton", background="#2563EB", foreground="#FFFFFF", font=("Segoe UI", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#1D4ED8")])
        
        style.configure("Success.TButton", background="#059669", foreground="#FFFFFF", font=("Segoe UI", 10, "bold"))
        style.map("Success.TButton", background=[("active", "#047857")])
        
        style.configure("Danger.TButton", background="#DC2626", foreground="#FFFFFF", font=("Segoe UI", 9, "bold"))
        style.map("Danger.TButton", background=[("active", "#B91C1C")])
        
        # Treeview styling
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#E2E8F0", foreground="#0F172A")
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 9))
        style.map("Treeview", background=[("selected", "#3B82F6")], foreground=[("selected", "#FFFFFF")])
        
    def _build_layout(self):
        # 1. Header Frame
        header = ttk.Frame(self.root, style="Header.TFrame", padding=14)
        header.pack(fill="x", side="top")
        
        title_label = tk.Label(
            header,
            text="CPU SCHEDULING SIMULATOR: PRIORITY VS MULTILEVEL QUEUE (MLQ)",
            font=("Segoe UI", 15, "bold"),
            bg="#1E293B",
            fg="#F8FAFC"
        )
        title_label.pack(anchor="w")
        
        sub_label = tk.Label(
            header,
            text="SLA Review Stage 2 | Shah & Anchor Kutchhi Engineering College | Guide: Prof. Deepshikha Chaturvedi",
            font=("Segoe UI", 9),
            bg="#1E293B",
            fg="#94A3B8"
        )
        sub_label.pack(anchor="w")
        
        # 2. Main Content Container
        main_container = ttk.Frame(self.root, padding=12)
        main_container.pack(fill="both", expand=True)
        
        # Top Half: Input & Process List
        top_pane = ttk.Frame(main_container)
        top_pane.pack(fill="x", pady=(0, 10))
        
        # Input Controls Card
        input_card = ttk.LabelFrame(top_pane, text=" Process Input & Queue Configuration ", padding=10)
        input_card.pack(side="left", fill="both", padx=(0, 10))
        
        grid_opts = {"padx": 5, "pady": 4, "sticky": "w"}
        
        # Process ID
        ttk.Label(input_card, text="Process ID:").grid(row=0, column=0, **grid_opts)
        self.entry_pid = ttk.Entry(input_card, width=12)
        self.entry_pid.grid(row=0, column=1, **grid_opts)
        self.entry_pid.insert(0, "P6")
        
        # Arrival Time
        ttk.Label(input_card, text="Arrival Time (AT):").grid(row=1, column=0, **grid_opts)
        self.entry_at = ttk.Entry(input_card, width=12)
        self.entry_at.grid(row=1, column=1, **grid_opts)
        self.entry_at.insert(0, "0")
        
        # Burst Time
        ttk.Label(input_card, text="Burst Time (BT):").grid(row=2, column=0, **grid_opts)
        self.entry_bt = ttk.Entry(input_card, width=12)
        self.entry_bt.grid(row=2, column=1, **grid_opts)
        self.entry_bt.insert(0, "4")
        
        # Priority
        ttk.Label(input_card, text="Priority (1 = Highest):").grid(row=3, column=0, **grid_opts)
        self.entry_priority = ttk.Entry(input_card, width=12)
        self.entry_priority.grid(row=3, column=1, **grid_opts)
        self.entry_priority.insert(0, "2")
        
        # Queue Selection
        ttk.Label(input_card, text="Queue Assignment:").grid(row=4, column=0, **grid_opts)
        self.combo_queue = ttk.Combobox(
            input_card,
            values=["System (Q1 - Priority)", "Interactive (Q2 - RR)", "Background (Q3 - FCFS)"],
            width=20,
            state="readonly"
        )
        self.combo_queue.grid(row=4, column=1, **grid_opts)
        self.combo_queue.current(1)
        
        # Input Action Buttons
        btn_box = ttk.Frame(input_card)
        btn_box.grid(row=5, column=0, columnspan=2, pady=(10, 0), sticky="ew")
        
        ttk.Button(btn_box, text="+ Add Process", style="Primary.TButton", command=self.add_process).pack(side="left", padx=2, fill="x", expand=True)
        ttk.Button(btn_box, text="Delete Selected", command=self.delete_selected_process).pack(side="left", padx=2, fill="x", expand=True)
        ttk.Button(btn_box, text="Clear All", command=self.clear_all_processes).pack(side="left", padx=2, fill="x", expand=True)
        
        # Presets Box
        preset_box = ttk.Frame(input_card)
        preset_box.grid(row=6, column=0, columnspan=2, pady=(8, 0), sticky="ew")
        ttk.Button(preset_box, text="Load Stage 1 Benchmark", command=self.load_benchmark_dataset).pack(side="left", padx=2, fill="x", expand=True)
        ttk.Button(preset_box, text="Load CPU Idle Case", command=self.load_idle_case).pack(side="left", padx=2, fill="x", expand=True)
        
        # Queued Process Table
        table_card = ttk.LabelFrame(top_pane, text=" Configured Process Workload ", padding=8)
        table_card.pack(side="right", fill="both", expand=True)
        
        table_cols = ("pid", "at", "bt", "priority", "queue")
        self.proc_tree = ttk.Treeview(table_card, columns=table_cols, show="headings", height=7)
        self.proc_tree.heading("pid", text="Process ID")
        self.proc_tree.heading("at", text="Arrival Time (AT)")
        self.proc_tree.heading("bt", text="Burst Time (BT)")
        self.proc_tree.heading("priority", text="Priority")
        self.proc_tree.heading("queue", text="Queue Type")
        
        self.proc_tree.column("pid", width=90, anchor="center")
        self.proc_tree.column("at", width=120, anchor="center")
        self.proc_tree.column("bt", width=120, anchor="center")
        self.proc_tree.column("priority", width=100, anchor="center")
        self.proc_tree.column("queue", width=150, anchor="center")
        
        scroll = ttk.Scrollbar(table_card, orient="vertical", command=self.proc_tree.yview)
        self.proc_tree.configure(yscrollcommand=scroll.set)
        self.proc_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        # 3. Execution Control & Algorithm Selection Bar
        ctrl_bar = ttk.LabelFrame(main_container, text=" Simulation Execution & Control ", padding=10)
        ctrl_bar.pack(fill="x", pady=(0, 10))
        
        ttk.Label(ctrl_bar, text="Select Algorithm Mode:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(5, 10))
        
        self.algo_choice = tk.StringVar(value="mlq")
        ttk.Radiobutton(ctrl_bar, text="1. Priority Scheduling", variable=self.algo_choice, value="priority").pack(side="left", padx=10)
        ttk.Radiobutton(ctrl_bar, text="2. Multilevel Queue (MLQ)", variable=self.algo_choice, value="mlq").pack(side="left", padx=10)
        ttk.Radiobutton(ctrl_bar, text="3. Compare Both Side-by-Side", variable=self.algo_choice, value="compare").pack(side="left", padx=10)
        
        ttk.Separator(ctrl_bar, orient="vertical").pack(side="left", fill="y", padx=15)
        
        ttk.Label(ctrl_bar, text="MLQ Q2 Quantum:").pack(side="left", padx=(0, 5))
        self.entry_quantum = ttk.Spinbox(ctrl_bar, from_=1, to=20, width=5)
        self.entry_quantum.set("2")
        self.entry_quantum.pack(side="left", padx=(0, 15))
        
        ttk.Button(ctrl_bar, text="▶ Run Simulation", style="Success.TButton", command=self.run_simulation).pack(side="right", padx=5)
        ttk.Button(ctrl_bar, text="Reset View", command=self.reset_views).pack(side="right", padx=5)
        
        # 4. Results Notebook (Tabs)
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill="both", expand=True)
        
        # Tab 1: Gantt Chart
        self.tab_gantt = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_gantt, text=" Visual Gantt Chart ")
        self.gantt_canvas = GanttCanvas(self.tab_gantt, height=130)
        self.gantt_canvas.pack(fill="x", expand=False, pady=(0, 10))
        
        # Summary KPI Cards Frame under Gantt Chart
        self.kpi_frame = ttk.LabelFrame(self.tab_gantt, text=" Key Performance Indicators (KPIs) ", padding=10)
        self.kpi_frame.pack(fill="x")
        self.kpi_labels = {}
        kpi_metrics = [
            ("avg_wt", "Avg Waiting Time (WT):", "—"),
            ("avg_tat", "Avg Turnaround Time (TAT):", "—"),
            ("avg_rt", "Avg Response Time (RT):", "—"),
            ("cpu_util", "CPU Utilization:", "—"),
            ("throughput", "Throughput:", "—")
        ]
        for idx, (key, title, default_val) in enumerate(kpi_metrics):
            card = ttk.Frame(self.kpi_frame, padding=6)
            card.pack(side="left", fill="both", expand=True)
            ttk.Label(card, text=title, font=("Segoe UI", 9, "bold"), foreground="#475569").pack()
            lbl = ttk.Label(card, text=default_val, font=("Segoe UI", 12, "bold"), foreground="#0F172A")
            lbl.pack()
            self.kpi_labels[key] = lbl
        
        # Tab 2: Detailed Process Metrics Table
        self.tab_table = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_table, text=" Detailed Results Table ")
        
        res_cols = ("pid", "at", "bt", "prio", "queue", "ct", "tat", "wt", "rt")
        self.res_tree = ttk.Treeview(self.tab_table, columns=res_cols, show="headings")
        self.res_tree.heading("pid", text="Process ID")
        self.res_tree.heading("at", text="Arrival Time (AT)")
        self.res_tree.heading("bt", text="Burst Time (BT)")
        self.res_tree.heading("prio", text="Priority")
        self.res_tree.heading("queue", text="Queue Type")
        self.res_tree.heading("ct", text="Completion Time (CT)")
        self.res_tree.heading("tat", text="Turnaround Time (TAT)")
        self.res_tree.heading("wt", text="Waiting Time (WT)")
        self.res_tree.heading("rt", text="Response Time (RT)")
        
        for c in res_cols:
            self.res_tree.column(c, anchor="center")
            
        res_scroll = ttk.Scrollbar(self.tab_table, orient="vertical", command=self.res_tree.yview)
        self.res_tree.configure(yscrollcommand=res_scroll.set)
        self.res_tree.pack(side="left", fill="both", expand=True)
        res_scroll.pack(side="right", fill="y")
        
        # Tab 3: Side-by-Side Comparison
        self.tab_compare = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_compare, text=" Side-by-Side Algorithm Comparison ")
        self._build_comparison_tab()
        
    def _build_comparison_tab(self):
        # Comparison Table
        lbl_info = ttk.Label(
            self.tab_compare,
            text="Comprehensive Comparative Performance Analysis on Selected Workload",
            font=("Segoe UI", 11, "bold"),
            foreground="#1E293B"
        )
        lbl_info.pack(anchor="w", pady=(0, 10))
        
        comp_cols = ("metric", "prio_val", "mlq_val", "delta", "evaluation")
        self.comp_tree = ttk.Treeview(self.tab_compare, columns=comp_cols, show="headings", height=6)
        self.comp_tree.heading("metric", text="Performance Metric")
        self.comp_tree.heading("prio_val", text="Priority Scheduling")
        self.comp_tree.heading("mlq_val", text="Multilevel Queue (MLQ)")
        self.comp_tree.heading("delta", text="Difference (Delta)")
        self.comp_tree.heading("evaluation", text="Analytical Observation")
        
        self.comp_tree.column("metric", width=220, anchor="w")
        self.comp_tree.column("prio_val", width=150, anchor="center")
        self.comp_tree.column("mlq_val", width=170, anchor="center")
        self.comp_tree.column("delta", width=140, anchor="center")
        self.comp_tree.column("evaluation", width=340, anchor="w")
        self.comp_tree.pack(fill="x", pady=(0, 15))
        
        # Text explanation card
        analysis_card = ttk.LabelFrame(self.tab_compare, text=" Architectural Evaluation & Theoretical Insights ", padding=12)
        analysis_card.pack(fill="both", expand=True)
        
        self.txt_analysis = tk.Text(analysis_card, wrap="word", font=("Segoe UI", 9), height=7, bg="#F8FAFC", relief="flat")
        self.txt_analysis.pack(fill="both", expand=True)
        self.txt_analysis.insert(
            "1.0",
            "Select 'Compare Both Side-by-Side' and click 'Run Simulation' to execute both algorithms on the "
            "active workload and generate an automated comparative analysis."
        )
        self.txt_analysis.config(state="disabled")

    # ==========================================================================
    # INPUT VALIDATION & HANDLING
    # ==========================================================================
    
    def add_process(self):
        """
        Validates user input and appends a new process to the active list.
        Handles negative numbers, empty inputs, non-integers, and duplicate PIDs.
        """
        pid = self.entry_pid.get().strip()
        at_str = self.entry_at.get().strip()
        bt_str = self.entry_bt.get().strip()
        prio_str = self.entry_priority.get().strip()
        q_raw = self.combo_queue.get()
        
        # 1. Non-empty check
        if not pid or not at_str or not bt_str or not prio_str:
            messagebox.showerror("Input Error", "All fields are required. Please fill in Process ID, AT, BT, and Priority.")
            return
            
        # 2. Duplicate PID check
        if any(p.pid.lower() == pid.lower() for p in self.processes):
            messagebox.showerror("Input Error", f"Process ID '{pid}' already exists. Process IDs must be unique.")
            return
            
        # 3. Numeric validation
        try:
            at = int(at_str)
            bt = int(bt_str)
            prio = int(prio_str)
        except ValueError:
            messagebox.showerror("Input Error", "Arrival Time, Burst Time, and Priority must be valid integers.")
            return
            
        # 4. Logical boundary conditions
        if at < 0:
            messagebox.showerror("Validation Error", "Arrival Time cannot be negative.")
            return
        if bt <= 0:
            messagebox.showerror("Validation Error", "Burst Time must be strictly greater than 0.")
            return
        if prio <= 0:
            messagebox.showerror("Validation Error", "Priority value must be a positive integer (e.g., 1, 2, 3...).")
            return
            
        # Map queue selection string to standard keyword
        queue_type = "System"
        if "Interactive" in q_raw:
            queue_type = "Interactive"
        elif "Background" in q_raw:
            queue_type = "Background"
            
        new_proc = Process(pid=pid, arrival_time=at, burst_time=bt, priority=prio, queue_type=queue_type)
        self.processes.append(new_proc)
        self._refresh_process_tree()
        
        # Auto-increment PID for next entry convenience
        try:
            prefix = "".join(filter(str.isalpha, pid)) or "P"
            num = int("".join(filter(str.isdigit, pid))) + 1
            self.entry_pid.delete(0, tk.END)
            self.entry_pid.insert(0, f"{prefix}{num}")
        except Exception:
            pass

    def delete_selected_process(self):
        selected = self.proc_tree.selection()
        if not selected:
            messagebox.showwarning("Selection Warning", "Please select a process from the workload table to remove.")
            return
        for item in selected:
            vals = self.proc_tree.item(item, "values")
            pid = vals[0]
            self.processes = [p for p in self.processes if p.pid != pid]
        self._refresh_process_tree()

    def clear_all_processes(self):
        if not self.processes:
            return
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all processes from the workload?"):
            self.processes.clear()
            self._refresh_process_tree()
            self.reset_views()

    def _refresh_process_tree(self):
        for row in self.proc_tree.get_children():
            self.proc_tree.delete(row)
        for p in sorted(self.processes, key=lambda x: (x.arrival_time, x.pid)):
            self.proc_tree.insert("", "end", values=(p.pid, p.arrival_time, p.burst_time, p.priority, p.queue_type))

    def load_benchmark_dataset(self):
        """Loads the official Stage 1 SLA benchmark workload."""
        self.processes = [
            Process("P1", arrival_time=0, burst_time=5, priority=1, queue_type="System"),
            Process("P2", arrival_time=1, burst_time=3, priority=2, queue_type="Interactive"),
            Process("P3", arrival_time=2, burst_time=8, priority=4, queue_type="Background"),
            Process("P4", arrival_time=3, burst_time=2, priority=1, queue_type="System"),
            Process("P5", arrival_time=4, burst_time=4, priority=3, queue_type="Interactive"),
        ]
        self._refresh_process_tree()
        self.entry_pid.delete(0, tk.END)
        self.entry_pid.insert(0, "P6")

    def load_idle_case(self):
        """Loads a workload featuring intermittent arrivals to test CPU idle handling."""
        self.processes = [
            Process("P1", arrival_time=0, burst_time=3, priority=1, queue_type="System"),
            Process("P2", arrival_time=6, burst_time=4, priority=2, queue_type="Interactive"),
            Process("P3", arrival_time=14, burst_time=5, priority=3, queue_type="Background"),
        ]
        self._refresh_process_tree()
        self.entry_pid.delete(0, tk.END)
        self.entry_pid.insert(0, "P4")

    def reset_views(self):
        self.gantt_canvas.delete("all")
        for k in self.kpi_labels:
            self.kpi_labels[k].config(text="—")
        for row in self.res_tree.get_children():
            self.res_tree.delete(row)
        for row in self.comp_tree.get_children():
            self.comp_tree.delete(row)
        self.txt_analysis.config(state="normal")
        self.txt_analysis.delete("1.0", tk.END)
        self.txt_analysis.insert("1.0", "Simulation reset. Ready for next run.")
        self.txt_analysis.config(state="disabled")

    # ==========================================================================
    # SIMULATION CONTROLLERS
    # ==========================================================================
    
    def run_simulation(self):
        if not self.processes:
            messagebox.showwarning("Empty Workload", "Please add processes or click 'Load Stage 1 Benchmark' before executing.")
            return
            
        try:
            quantum = int(self.entry_quantum.get().strip())
            if quantum <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Input Error", "MLQ Time Quantum must be a positive integer.")
            return

        mode = self.algo_choice.get()
        
        if mode == "priority":
            gantt, procs, metrics = PriorityScheduler.schedule(self.processes)
            self._render_single_algorithm(gantt, procs, metrics, "Priority Scheduling (Non-Preemptive)")
            self.notebook.select(self.tab_gantt)
            
        elif mode == "mlq":
            gantt, procs, metrics = MultilevelQueueScheduler.schedule(self.processes, quantum=quantum)
            self._render_single_algorithm(gantt, procs, metrics, f"Multilevel Queue Scheduling (Time Quantum = {quantum})")
            self.notebook.select(self.tab_gantt)
            
        elif mode == "compare":
            gantt_p, procs_p, metrics_p = PriorityScheduler.schedule(self.processes)
            gantt_m, procs_m, metrics_m = MultilevelQueueScheduler.schedule(self.processes, quantum=quantum)
            self._render_comparison(metrics_p, metrics_m, quantum)
            # Default to Gantt of MLQ and select Compare tab
            self._render_single_algorithm(gantt_m, procs_m, metrics_m, f"MLQ Simulation (Shown in Gantt) | Comparative Mode Active")
            self.notebook.select(self.tab_compare)

    def _render_single_algorithm(self, gantt: List[GanttBlock], procs: List[Process], metrics: Dict[str, float], title: str):
        # 1. Draw Gantt Chart
        self.gantt_canvas.draw_gantt(gantt)
        
        # 2. Update KPI Cards
        self.kpi_labels["avg_wt"].config(text=f"{metrics['avg_waiting_time']} ms")
        self.kpi_labels["avg_tat"].config(text=f"{metrics['avg_turnaround_time']} ms")
        self.kpi_labels["avg_rt"].config(text=f"{metrics['avg_response_time']} ms")
        self.kpi_labels["cpu_util"].config(text=f"{metrics['cpu_utilization']}%")
        self.kpi_labels["throughput"].config(text=f"{metrics['throughput']} proc/ms")
        
        # 3. Populate Results Table
        for row in self.res_tree.get_children():
            self.res_tree.delete(row)
            
        for p in sorted(procs, key=lambda x: (x.completion_time, x.pid)):
            self.res_tree.insert(
                "", "end",
                values=(
                    p.pid, p.arrival_time, p.burst_time, p.priority, p.queue_type,
                    p.completion_time, p.turnaround_time, p.waiting_time, p.response_time
                )
            )

    def _render_comparison(self, m_prio: Dict[str, float], m_mlq: Dict[str, float], quantum: int):
        for row in self.comp_tree.get_children():
            self.comp_tree.delete(row)
            
        # Comparison parameters
        rows = [
            (
                "Average Waiting Time (WT)",
                f"{m_prio['avg_waiting_time']} ms",
                f"{m_mlq['avg_waiting_time']} ms",
                f"{round(m_mlq['avg_waiting_time'] - m_prio['avg_waiting_time'], 2):+g} ms",
                "Priority favors short/high priority bursts; MLQ introduces slice interleaving."
            ),
            (
                "Average Turnaround Time (TAT)",
                f"{m_prio['avg_turnaround_time']} ms",
                f"{m_mlq['avg_turnaround_time']} ms",
                f"{round(m_mlq['avg_turnaround_time'] - m_prio['avg_turnaround_time'], 2):+g} ms",
                "Closely matched; MLQ prioritizes responsiveness over batch completion."
            ),
            (
                "Average Response Time (RT)",
                f"{m_prio['avg_response_time']} ms",
                f"{m_mlq['avg_response_time']} ms",
                f"{round(m_mlq['avg_response_time'] - m_prio['avg_response_time'], 2):+g} ms",
                "MLQ provides faster initial CPU access to interactive processes via Round Robin."
            ),
            (
                "CPU Utilization",
                f"{m_prio['cpu_utilization']}%",
                f"{m_mlq['cpu_utilization']}%",
                f"{round(m_mlq['cpu_utilization'] - m_prio['cpu_utilization'], 2):+g}%",
                "Both algorithms maintain maximum CPU saturation when processes are available."
            ),
            (
                "Throughput",
                f"{m_prio['throughput']} p/ms",
                f"{m_mlq['throughput']} p/ms",
                f"{round(m_mlq['throughput'] - m_prio['throughput'], 4):+g} p/ms",
                "Identical total schedule makespan on finite batch workloads."
            ),
        ]
        
        for r in rows:
            self.comp_tree.insert("", "end", values=r)
            
        # Analytical Text
        self.txt_analysis.config(state="normal")
        self.txt_analysis.delete("1.0", tk.END)
        narrative = (
            f"=== COMPARATIVE PERFORMANCE EVALUATION REPORT ===\n\n"
            f"1. Responsiveness & Fairness (Response Time):\n"
            f"   - Multilevel Queue (MLQ) achieves an Average Response Time of {m_mlq['avg_response_time']} ms, "
            f"compared to {m_prio['avg_response_time']} ms under Priority Scheduling.\n"
            f"   - Insight: By assigning Interactive processes to Queue 2 governed by Round Robin (Quantum = {quantum}), "
            f"interactive tasks receive rapid initial CPU slices rather than waiting for preceding medium/long tasks.\n\n"
            f"2. Waiting Time & Scheduling Overhead:\n"
            f"   - Priority Scheduling yielded an Average Waiting Time of {m_prio['avg_waiting_time']} ms, "
            f"versus {m_mlq['avg_waiting_time']} ms in MLQ.\n"
            f"   - Insight: Non-preemptive priority execution completes runnable tasks in a single burst, avoiding the "
            f"interleaved delay that occurs when processes share slices within intermediate queues.\n\n"
            f"3. Starvation Vulnerability & Architectural Transition to Stage 3:\n"
            f"   - Traditional MLQ assigns static queue memberships: background processes (Queue 3) can suffer from indefinite "
            f"starvation if system and interactive processes continuously arrive.\n"
            f"   - This empirical observation validates the research rationale for Stage 3: implementing Multi-Queue "
            f"Adaptive Priority Scheduling (MQAPS) with dynamic aging and inter-queue migrations."
        )
        self.txt_analysis.insert("1.0", narrative)
        self.txt_analysis.config(state="disabled")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main():
    root = tk.Tk()
    app = CPUSchedulingSimulatorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
