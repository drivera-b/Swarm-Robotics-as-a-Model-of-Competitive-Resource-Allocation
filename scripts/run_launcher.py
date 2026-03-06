#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.config import save_config
    from src.discovery import scan_bolts
except Exception:
    save_config = None  # type: ignore[assignment]
    scan_bolts = None  # type: ignore[assignment]


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sphero STEM Expo Launcher")
        self.geometry("1120x720")
        self.minsize(980, 640)

        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.discovered_devices: list[dict[str, str]] = []

        self.num_robots = tk.StringVar(value="3")
        self.scan_timeout = tk.StringVar(value="10")
        self.speed = tk.StringVar(value="35")
        self.roll_seconds = tk.StringVar(value="1")
        self.cycles = tk.StringVar(value="2")
        self.lambda_value = tk.StringVar(value="2")
        self.crowding_mode = tk.StringVar(value="inferred")
        self.decision_min = tk.StringVar(value="2")
        self.decision_max = tk.StringVar(value="3")
        self.trial_seconds = tk.StringVar(value="90")
        self.discovery_select = tk.StringVar(value="1,2,3")
        self.status_text = tk.StringVar(value="Idle")

        self._build_ui()
        self.after(100, self._flush_output)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        params = ttk.LabelFrame(root, text="Parameters", padding=8)
        params.pack(fill=tk.X)

        controls = [
            ("Num Robots", self.num_robots),
            ("Scan Timeout", self.scan_timeout),
            ("Speed", self.speed),
            ("Roll Seconds", self.roll_seconds),
            ("MVP Cycles", self.cycles),
            ("Lambda (2/6/10)", self.lambda_value),
            ("Crowding Mode", self.crowding_mode),
            ("Decision Min", self.decision_min),
            ("Decision Max", self.decision_max),
            ("Trial Seconds", self.trial_seconds),
            ("Discovery Select", self.discovery_select),
        ]

        for i, (label, var) in enumerate(controls):
            row = i // 3
            col = (i % 3) * 2
            ttk.Label(params, text=label).grid(row=row, column=col, sticky=tk.W, padx=(0, 6), pady=4)
            if label == "Crowding Mode":
                box = ttk.Combobox(
                    params,
                    values=["inferred", "manual"],
                    textvariable=var,
                    width=16,
                    state="readonly",
                )
                box.grid(row=row, column=col + 1, sticky=tk.W, pady=4)
            else:
                ttk.Entry(params, textvariable=var, width=18).grid(
                    row=row, column=col + 1, sticky=tk.W, pady=4
                )

        buttons = ttk.LabelFrame(root, text="Actions", padding=8)
        buttons.pack(fill=tk.X, pady=(10, 0))

        self.btn_scan = ttk.Button(buttons, text="Discovery (Scan Only)", command=self._run_scan_only)
        self.btn_discovery_save = ttk.Button(buttons, text="Discovery (Save Selection)", command=self._run_discovery_save)
        self.btn_select_gui = ttk.Button(
            buttons,
            text="Select Robots (GUI)",
            command=self._open_robot_selector,
        )
        self.btn_mvp = ttk.Button(buttons, text="Run MVP", command=self._run_mvp)
        self.btn_trial = ttk.Button(buttons, text="Run Trial", command=self._run_trial)
        self.btn_trial_l2 = ttk.Button(
            buttons,
            text="Run Trial (lambda=2, inferred)",
            command=lambda: self._run_trial_fixed_lambda("2"),
        )
        self.btn_trial_l6 = ttk.Button(
            buttons,
            text="Run Trial (lambda=6, inferred)",
            command=lambda: self._run_trial_fixed_lambda("6"),
        )
        self.btn_trial_l10 = ttk.Button(
            buttons,
            text="Run Trial (lambda=10, inferred)",
            command=lambda: self._run_trial_fixed_lambda("10"),
        )
        self.btn_stop = ttk.Button(buttons, text="Emergency Stop", command=self._run_stop)
        self.btn_interrupt = ttk.Button(buttons, text="Interrupt", command=self._interrupt_running)

        self.btn_scan.grid(row=0, column=0, padx=4, pady=4, sticky=tk.W)
        self.btn_discovery_save.grid(row=0, column=1, padx=4, pady=4, sticky=tk.W)
        self.btn_select_gui.grid(row=0, column=2, padx=4, pady=4, sticky=tk.W)
        self.btn_mvp.grid(row=1, column=0, padx=4, pady=4, sticky=tk.W)
        self.btn_trial.grid(row=1, column=1, padx=4, pady=4, sticky=tk.W)
        self.btn_trial_l2.grid(row=1, column=2, padx=4, pady=4, sticky=tk.W)
        self.btn_trial_l6.grid(row=1, column=3, padx=4, pady=4, sticky=tk.W)
        self.btn_trial_l10.grid(row=1, column=4, padx=4, pady=4, sticky=tk.W)
        self.btn_stop.grid(row=2, column=0, padx=4, pady=4, sticky=tk.W)
        self.btn_interrupt.grid(row=2, column=1, padx=4, pady=4, sticky=tk.W)

        status = ttk.Frame(root, padding=(0, 8))
        status.pack(fill=tk.X)
        ttk.Label(status, text="Status:").pack(side=tk.LEFT)
        ttk.Label(status, textvariable=self.status_text).pack(side=tk.LEFT, padx=(4, 0))

        log_frame = ttk.LabelFrame(root, text="Output", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.output_text = tk.Text(log_frame, wrap=tk.WORD, height=20)
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.output_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=scrollbar.set)

        self._log(
            "Launcher ready.\n"
            "Tip: use Select Robots (GUI) for point-and-click selection, then run MVP/Trial.\n"
        )

    def _log(self, text: str) -> None:
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)

    def _read_stream(self, stream) -> None:
        try:
            assert stream is not None
            for line in iter(stream.readline, ""):
                self.output_queue.put(line)
        finally:
            self.output_queue.put("__PROCESS_ENDED__")

    def _flush_output(self) -> None:
        while True:
            try:
                item = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if item == "__PROCESS_ENDED__":
                self._on_process_ended()
            else:
                self._log(item)
        self.after(100, self._flush_output)

    def _validate_common(self) -> bool:
        try:
            int(self.num_robots.get())
            float(self.scan_timeout.get())
            int(self.speed.get())
            float(self.roll_seconds.get())
            int(self.cycles.get())
            int(self.trial_seconds.get())
            float(self.decision_min.get())
            float(self.decision_max.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "One or more numeric parameters are invalid.")
            return False

        if self.lambda_value.get() not in {"2", "6", "10"}:
            messagebox.showerror("Invalid Input", "Lambda must be 2, 6, or 10.")
            return False
        if self.crowding_mode.get() not in {"inferred", "manual"}:
            messagebox.showerror("Invalid Input", "Crowding mode must be inferred or manual.")
            return False
        return True

    def _run_scan_only(self) -> None:
        if not self._validate_common():
            return
        cmd = [
            "scripts/run_discovery.py",
            "--timeout",
            self.scan_timeout.get(),
            "--list-only",
        ]
        self._start_command(cmd, "Running discovery scan...")

    def _run_discovery_save(self) -> None:
        if not self._validate_common():
            return
        select_value = self.discovery_select.get().strip()
        if not select_value:
            messagebox.showerror(
                "Selection Required",
                "Enter Discovery Select (example: 1,2,3 or robot names/addresses).",
            )
            return
        cmd = [
            "scripts/run_discovery.py",
            "--timeout",
            self.scan_timeout.get(),
            "--select",
            select_value,
        ]
        self._start_command(cmd, "Saving selected robots to config.json...")

    def _open_robot_selector(self) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showwarning("Process Running", "Interrupt current command first.")
            return
        if scan_bolts is None or save_config is None:
            messagebox.showerror(
                "Unavailable",
                "GUI robot selector is unavailable because discovery modules did not import.",
            )
            return

        selector = tk.Toplevel(self)
        selector.title("Select Robots")
        selector.geometry("760x460")
        selector.transient(self)
        selector.grab_set()

        container = ttk.Frame(selector, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        top_row = ttk.Frame(container)
        top_row.pack(fill=tk.X)

        timeout_var = tk.StringVar(value=self.scan_timeout.get())
        status_var = tk.StringVar(value="Click Scan Nearby to discover robots.")

        ttk.Label(top_row, text="Scan Timeout (s)").pack(side=tk.LEFT)
        ttk.Entry(top_row, textvariable=timeout_var, width=8).pack(side=tk.LEFT, padx=(6, 12))

        list_frame = ttk.Frame(container)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 8))

        listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)

        def scan_now() -> None:
            try:
                timeout = float(timeout_var.get())
            except ValueError:
                messagebox.showerror("Invalid Input", "Scan timeout must be a number.")
                return
            status_var.set("Scanning...")
            selector.update_idletasks()
            try:
                devices = scan_bolts(timeout=timeout)
            except Exception as exc:
                status_var.set(f"Scan failed: {exc}")
                self._log(f"GUI scan failed: {exc}\n")
                return

            self.discovered_devices = devices
            listbox.delete(0, tk.END)
            for idx, device in enumerate(devices, start=1):
                name = device.get("name", "UNKNOWN")
                address = device.get("address", "")
                listbox.insert(tk.END, f"{idx:>2}. {name:<18}  {address}")

            if not devices:
                status_var.set("No BOLT robots found.")
                return
            status_var.set(f"Found {len(devices)} robots. Multi-select then click Save Selection.")

        def save_selected_from_list() -> None:
            indices = listbox.curselection()
            if not indices:
                messagebox.showerror("No Selection", "Select one or more robots from the list.")
                return
            selected = [self.discovered_devices[i] for i in indices]
            try:
                save_config(PROJECT_ROOT / "config.json", {"robots": selected})
            except Exception as exc:
                messagebox.showerror("Save Failed", str(exc))
                return

            selection_text = ",".join(str(i + 1) for i in indices)
            self.discovery_select.set(selection_text)
            status_var.set(f"Saved {len(selected)} robot(s) to config.json")
            self._log(f"Saved {len(selected)} robot(s) to config.json via GUI selector.\n")
            messagebox.showinfo("Saved", f"Saved {len(selected)} robot(s) to config.json")

        button_row = ttk.Frame(container)
        button_row.pack(fill=tk.X)
        ttk.Button(button_row, text="Scan Nearby", command=scan_now).pack(side=tk.LEFT)
        ttk.Button(button_row, text="Save Selection", command=save_selected_from_list).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(button_row, text="Close", command=selector.destroy).pack(side=tk.RIGHT)

        ttk.Label(container, textvariable=status_var).pack(fill=tk.X, pady=(8, 0))

    def _run_mvp(self) -> None:
        if not self._validate_common():
            return
        cmd = [
            "scripts/run_mvp.py",
            "--num-robots",
            self.num_robots.get(),
            "--speed",
            self.speed.get(),
            "--roll-seconds",
            self.roll_seconds.get(),
            "--cycles",
            self.cycles.get(),
            "--scan-timeout",
            self.scan_timeout.get(),
        ]
        self._start_command(cmd, "Running MVP test...")

    def _run_trial(self) -> None:
        if not self._validate_common():
            return
        cmd = self._build_trial_command(
            lambda_value=self.lambda_value.get(),
            crowding_mode=self.crowding_mode.get(),
        )
        self._start_command(cmd, "Running trial...")

    def _run_trial_fixed_lambda(self, lambda_value: str) -> None:
        if not self._validate_common():
            return
        cmd = self._build_trial_command(lambda_value=lambda_value, crowding_mode="inferred")
        self._start_command(
            cmd,
            f"Running trial (lambda={lambda_value}, crowding=inferred)...",
        )

    def _build_trial_command(self, *, lambda_value: str, crowding_mode: str) -> list[str]:
        cmd = [
            "scripts/run_trial.py",
            "--num-robots",
            self.num_robots.get(),
            "--lambda-value",
            lambda_value,
            "--crowding-mode",
            crowding_mode,
            "--trial-seconds",
            self.trial_seconds.get(),
            "--speed",
            self.speed.get(),
            "--roll-seconds",
            self.roll_seconds.get(),
            "--decision-min",
            self.decision_min.get(),
            "--decision-max",
            self.decision_max.get(),
            "--scan-timeout",
            self.scan_timeout.get(),
        ]
        return cmd

    def _run_stop(self) -> None:
        if not self._validate_common():
            return
        cmd = [
            "scripts/run_stop.py",
            "--num-robots",
            self.num_robots.get(),
            "--scan-timeout",
            self.scan_timeout.get(),
        ]
        self._start_command(cmd, "Sending emergency stop...")

    def _start_command(self, script_args: list[str], status: str) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showwarning("Process Running", "A command is already running. Interrupt it first.")
            return

        command = [sys.executable, *script_args]
        self._log(f"\n$ {' '.join(command)}\n")
        self.status_text.set(status)

        kwargs: dict[str, object] = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            kwargs["start_new_session"] = True

        self.process = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            **kwargs,
        )
        thread = threading.Thread(
            target=self._read_stream,
            args=(self.process.stdout,),
            daemon=True,
        )
        thread.start()

    def _interrupt_running(self) -> None:
        if not self.process or self.process.poll() is not None:
            self._log("No running command to interrupt.\n")
            return
        try:
            if os.name == "nt":
                self.process.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            else:
                os.killpg(self.process.pid, signal.SIGINT)
            self._log("Interrupt signal sent.\n")
        except Exception as exc:
            self._log(f"Interrupt failed: {exc}\n")

    def _on_process_ended(self) -> None:
        if not self.process:
            return
        code = self.process.poll()
        if code is None:
            return
        self.status_text.set(f"Idle (last exit code: {code})")
        self._log(f"\n[process ended with code {code}]\n")
        self.process = None

    def _on_close(self) -> None:
        if self.process and self.process.poll() is None:
            should_close = messagebox.askyesno(
                "Exit Launcher",
                "A command is still running. Interrupt and close?",
            )
            if not should_close:
                return
            self._interrupt_running()
        self.destroy()


def main() -> int:
    app = LauncherApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
