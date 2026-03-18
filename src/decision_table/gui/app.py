"""Decision Table Editor - Professional single-window Tkinter GUI."""

from __future__ import annotations

import platform
import tkinter as tk
from tkinter import ttk, filedialog

from ..model import (
    Action, Condition, ConditionType, Constraint, ConstraintType,
    DecisionTable, Rule, TableType, DONT_CARE,
    make_boolean_condition, make_enum_condition, make_numeric_condition,
)
from ..serialization import load_file, save_file
from ..validation import Severity, validate_all
from ..reduction import quine_mccluskey, petricks_method, rule_merging, espresso, compare_reductions
from ..testing import (
    generate_test_cases, generate_boundary_tests, generate_pairwise_tests,
    generate_all_tests, calculate_coverage, export_test_cases_csv,
)

# ── Color palette ──
_CLR = {
    "bg":          "#f5f6fa",
    "toolbar_bg":  "#e8eaf0",
    "cond_hdr":    "#4a90d9",
    "cond_cell":   "#eaf2fb",
    "act_hdr":     "#5cb85c",
    "act_cell":    "#eaf7ea",
    "else_cell":   "#fff3cd",
    "else_hdr":    "#f0ad4e",
    "grid_hdr":    "#d0d4e0",
    "grid_hdr_fg": "#333344",
    "separator":   "#b0b8c8",
    "output_bg":   "#f8f9fc",
    "output_fg":   "#1a1a2e",
    "status_bg":   "#e0e3ea",
    "status_fg":   "#333344",
}

_FONT       = ("Segoe UI", 10) if platform.system() == "Windows" else ("SF Pro Text", 11)
_FONT_SMALL = (_FONT[0], _FONT[1] - 1)
_FONT_BOLD  = (_FONT[0], _FONT[1], "bold")
_FONT_MONO  = ("Consolas", 10) if platform.system() == "Windows" else ("Menlo", 11)
_FONT_GRID  = (_FONT[0], _FONT[1] - 1)
_FONT_GRID_B = (_FONT[0], _FONT[1] - 1, "bold")


class DecisionTableApp:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Decision Table Editor")
        self.root.geometry("1200x800")
        self.root.minsize(900, 550)
        self.root.configure(bg=_CLR["bg"])

        # Use ttk theme
        style = ttk.Style()
        available = style.theme_names()
        for pref in ("aqua", "clam", "vista", "xpnative"):
            if pref in available:
                style.theme_use(pref)
                break

        self.table = DecisionTable()
        self.current_file: str | None = None
        self.modified = False
        self._pre_reduce_rules: list[Rule] | None = None

        self._setup_ui()
        self._update_title()
        self._update_status()

    # ══════════════════════════════════════════════
    # UI Setup
    # ══════════════════════════════════════════════

    def _setup_ui(self):
        self._create_menu_bar()
        self._create_toolbar()

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status = tk.Label(
            self.root, textvariable=self.status_var, anchor=tk.W,
            bg=_CLR["status_bg"], fg=_CLR["status_fg"],
            font=_FONT_SMALL, padx=8, pady=3,
        )
        status.pack(side=tk.BOTTOM, fill=tk.X)

        # Main paned: top = editor, bottom = output
        paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        top = tk.Frame(paned, bg=_CLR["bg"])
        paned.add(top, weight=3)
        self._create_add_bar(top)
        self._create_table_editor(top)

        bottom = tk.Frame(paned, bg=_CLR["bg"])
        paned.add(bottom, weight=1)
        self._create_output_panel(bottom)

    # ══════════════════════════════════════════════
    # Menu Bar
    # ══════════════════════════════════════════════

    def _create_menu_bar(self):
        mb = tk.Menu(self.root)
        self.root.config(menu=mb)

        # ── File ──
        fm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="New Table", command=self.new_table, accelerator="Ctrl+N")
        fm.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        fm.add_separator()
        fm.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        fm.add_command(label="Save As...", command=self.save_file_as, accelerator="Ctrl+Shift+S")
        fm.add_separator()
        fm.add_command(label="Rename Table...", command=self._rename_table)
        fm.add_separator()
        fm.add_command(label="Exit", command=self.root.quit, accelerator="Ctrl+Q")

        # ── Edit ──
        em = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Edit", menu=em)
        em.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        em.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        em.add_separator()
        em.add_command(label="Add Rule", command=self.add_rule)
        em.add_command(label="Add Else Rule", command=self.add_else_rule)
        em.add_command(label="Duplicate Last Rule", command=self.duplicate_last_rule)
        em.add_command(label="Remove Last Rule", command=self.remove_last_rule)
        em.add_separator()
        em.add_command(label="Move Rule Left", command=lambda: self._move_rule(-1))
        em.add_command(label="Move Rule Right", command=lambda: self._move_rule(1))

        # ── Analysis ──
        am = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Analysis", menu=am)
        am.add_command(label="Validate All", command=self.run_validate, accelerator="F5")
        am.add_separator()
        am.add_command(label="Reduce (Quine-McCluskey)", command=lambda: self._run_reduce_method("qm"))
        am.add_command(label="Reduce (Petrick)", command=lambda: self._run_reduce_method("petrick"))
        am.add_command(label="Reduce (Rule Merging)", command=lambda: self._run_reduce_method("merge"))
        am.add_command(label="Reduce (Espresso)", command=lambda: self._run_reduce_method("espresso"))
        am.add_command(label="Undo Reduce", command=self.undo_reduce)
        am.add_separator()
        am.add_command(label="Compare All Methods", command=self.run_compare)
        am.add_command(label="Check Equivalence", command=self.run_equivalence)

        # ── Testing ──
        tm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Testing", menu=tm)
        tm.add_command(label="Generate All Tests", command=lambda: self.run_tests("all"), accelerator="F6")
        tm.add_command(label="Test Cases (per rule)", command=lambda: self.run_tests("normal"))
        tm.add_command(label="Boundary Value Tests", command=lambda: self.run_tests("boundary"))
        tm.add_command(label="Pairwise Tests", command=lambda: self.run_tests("pairwise"))
        tm.add_separator()
        tm.add_command(label="Export Tests to CSV...", command=self.export_tests)

        # ── Constraints ──
        cm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Constraints", menu=cm)
        cm.add_command(label="Add Exclusion...", command=lambda: self._add_constraint_inline("exclusion"))
        cm.add_command(label="Add Implication...", command=lambda: self._add_constraint_inline("implication"))
        cm.add_command(label="Add Impossible...", command=lambda: self._add_constraint_inline("impossible"))
        cm.add_separator()
        cm.add_command(label="List Constraints", command=self._list_constraints)
        cm.add_command(label="Remove Last Constraint", command=self._remove_last_constraint)

        # ── Help ──
        hm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Help", menu=hm)
        hm.add_command(label="Quick Start Guide", command=self._help_quickstart)
        hm.add_command(label="Keyboard Shortcuts", command=self._help_shortcuts)
        hm.add_separator()
        hm.add_command(label="Condition Types", command=self._help_condition_types)
        hm.add_command(label="Constraint Types", command=self._help_constraint_types)
        hm.add_command(label="Reduction Algorithms", command=self._help_reduction)
        hm.add_command(label="Test Generation", command=self._help_testing)
        hm.add_separator()
        hm.add_command(label="About", command=self._show_about)

        # Keybindings
        self.root.bind("<Control-n>", lambda e: self.new_table())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<F5>", lambda e: self.run_validate())
        self.root.bind("<F6>", lambda e: self.run_tests("all"))

    # ══════════════════════════════════════════════
    # Toolbar
    # ══════════════════════════════════════════════

    def _create_toolbar(self):
        tb = tk.Frame(self.root, bg=_CLR["toolbar_bg"], pady=2)
        tb.pack(side=tk.TOP, fill=tk.X)

        def _btn(parent, text, cmd):
            b = tk.Button(parent, text=text, command=cmd, relief=tk.FLAT,
                          bg=_CLR["toolbar_bg"], activebackground="#d0d4e0",
                          font=_FONT_SMALL, padx=8, pady=3, bd=0)
            b.pack(side=tk.LEFT, padx=1)
            return b

        def _sep(parent):
            f = tk.Frame(parent, width=1, bg=_CLR["separator"])
            f.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=3)

        _btn(tb, "New", self.new_table)
        _btn(tb, "Open", self.open_file)
        _btn(tb, "Save", self.save_file)
        _sep(tb)
        _btn(tb, "Undo", self.undo)
        _btn(tb, "Redo", self.redo)
        _sep(tb)
        _btn(tb, "+ Rule", self.add_rule)
        _btn(tb, "+ Else", self.add_else_rule)
        _btn(tb, "Copy", self.duplicate_last_rule)
        _btn(tb, "- Rule", self.remove_last_rule)
        _sep(tb)
        _btn(tb, "Validate", self.run_validate)
        _sep(tb)

        self.reduce_method = ttk.Combobox(tb, values=["Quine-McCluskey", "Petrick", "Rule Merging", "Espresso"],
                                          state="readonly", width=16, font=_FONT_SMALL)
        self.reduce_method.set("Quine-McCluskey")
        self.reduce_method.pack(side=tk.LEFT, padx=2, pady=1)
        _btn(tb, "Reduce", self.run_reduce)
        _btn(tb, "Undo Reduce", self.undo_reduce)
        _sep(tb)
        _btn(tb, "Tests", lambda: self.run_tests("all"))

    # ══════════════════════════════════════════════
    # Add Bar
    # ══════════════════════════════════════════════

    def _create_add_bar(self, parent):
        outer = tk.Frame(parent, bg=_CLR["bg"])
        outer.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6, 0))

        _lbl_kw = dict(bg="white", fg="#333344", font=_FONT_SMALL)
        _entry_kw = dict(bg="white", fg="#1a1a2e", font=_FONT_SMALL,
                         insertbackground="#1a1a2e", relief=tk.SOLID, bd=1,
                         highlightthickness=0, selectbackground="#d0d4e0",
                         selectforeground="#1a1a2e")
        _btn_kw = dict(bg="#e8eaf0", fg="#333344", font=_FONT_SMALL,
                       activebackground="#d0d4e0", relief=tk.RAISED, bd=1, padx=6)
        _list_kw = dict(font=_FONT_SMALL, bg="white", fg="#1a1a2e",
                        selectmode=tk.EXTENDED, highlightthickness=0,
                        relief=tk.SOLID, bd=1)

        # Three sections side by side
        sections = tk.Frame(outer, bg=_CLR["bg"])
        sections.pack(fill=tk.X)

        # ── Conditions section ──
        cond_frame = tk.LabelFrame(sections, text="  Conditions  ",
                                   bg="white", fg="#333344", font=_FONT_SMALL, padx=6, pady=4)
        cond_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))

        add_cond = tk.Frame(cond_frame, bg="white")
        add_cond.pack(fill=tk.X)
        tk.Label(add_cond, text="Name:", **_lbl_kw).pack(side=tk.LEFT)
        self.cond_name = tk.Entry(add_cond, width=14, **_entry_kw)
        self.cond_name.pack(side=tk.LEFT, padx=3)
        tk.Label(add_cond, text="Values:", **_lbl_kw).pack(side=tk.LEFT)
        self.cond_vals = tk.Entry(add_cond, width=12, **_entry_kw)
        self.cond_vals.insert(0, "T, F")
        self.cond_vals.pack(side=tk.LEFT, padx=3)
        tk.Label(add_cond, text="Type:", **_lbl_kw).pack(side=tk.LEFT)
        self.cond_type = ttk.Combobox(add_cond, values=["boolean", "enum", "numeric"],
                                      state="readonly", width=8, font=_FONT_SMALL)
        self.cond_type.set("boolean")
        self.cond_type.pack(side=tk.LEFT, padx=3)
        tk.Button(add_cond, text="Add", command=self._add_condition, **_btn_kw).pack(side=tk.LEFT, padx=3)

        rm_cond = tk.Frame(cond_frame, bg="white")
        rm_cond.pack(fill=tk.X, pady=(4, 0))
        self.remove_cond_list = tk.Listbox(rm_cond, width=40, height=3, **_list_kw)
        self.remove_cond_list.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(rm_cond, text="Remove\nSelected", command=self._remove_selected_conditions, **_btn_kw).pack(side=tk.LEFT, padx=(4, 0))

        # ── Actions section ──
        act_frame = tk.LabelFrame(sections, text="  Actions  ",
                                  bg="white", fg="#333344", font=_FONT_SMALL, padx=6, pady=4)
        act_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)

        add_act = tk.Frame(act_frame, bg="white")
        add_act.pack(fill=tk.X)
        tk.Label(add_act, text="Name:", **_lbl_kw).pack(side=tk.LEFT)
        self.act_name = tk.Entry(add_act, width=14, **_entry_kw)
        self.act_name.pack(side=tk.LEFT, padx=3)
        tk.Label(add_act, text="Values:", **_lbl_kw).pack(side=tk.LEFT)
        self.act_vals = tk.Entry(add_act, width=12, **_entry_kw)
        self.act_vals.insert(0, "X, ")
        self.act_vals.pack(side=tk.LEFT, padx=3)
        tk.Button(add_act, text="Add", command=self._add_action, **_btn_kw).pack(side=tk.LEFT, padx=3)

        rm_act = tk.Frame(act_frame, bg="white")
        rm_act.pack(fill=tk.X, pady=(4, 0))
        self.remove_act_list = tk.Listbox(rm_act, width=30, height=3, **_list_kw)
        self.remove_act_list.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(rm_act, text="Remove\nSelected", command=self._remove_selected_actions, **_btn_kw).pack(side=tk.LEFT, padx=(4, 0))

        # ── Rules section ──
        rule_frame = tk.LabelFrame(sections, text="  Rules  ",
                                   bg="white", fg="#333344", font=_FONT_SMALL, padx=6, pady=4)
        rule_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(3, 0))

        add_rule = tk.Frame(rule_frame, bg="white")
        add_rule.pack(fill=tk.X)
        tk.Button(add_rule, text="+ Rule", command=self.add_rule, **_btn_kw).pack(side=tk.LEFT, padx=2)
        tk.Button(add_rule, text="+ Else", command=self.add_else_rule, **_btn_kw).pack(side=tk.LEFT, padx=2)
        tk.Button(add_rule, text="Copy Last", command=self.duplicate_last_rule, **_btn_kw).pack(side=tk.LEFT, padx=2)

        rm_rule = tk.Frame(rule_frame, bg="white")
        rm_rule.pack(fill=tk.X, pady=(4, 0))
        self.remove_rule_list = tk.Listbox(rm_rule, width=30, height=3, **_list_kw)
        self.remove_rule_list.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(rm_rule, text="Remove\nSelected", command=self._remove_selected_rules, **_btn_kw).pack(side=tk.LEFT, padx=(4, 0))

    def _add_condition(self):
        name = self.cond_name.get().strip()
        if not name:
            return self._set_status("Enter a condition name.")
        vals = [v.strip() for v in self.cond_vals.get().split(",") if v.strip()] or ["T", "F"]
        ct = self.cond_type.get()
        try:
            if ct == "numeric":
                cond = make_numeric_condition(name, vals)
            elif ct == "enum":
                cond = make_enum_condition(name, vals)
            else:
                cond = make_boolean_condition(name)
            self.table.add_condition(cond)
            self.cond_name.delete(0, tk.END)
            self._refresh_editor()
            self.mark_modified()
        except ValueError as e:
            self._set_status(str(e))

    def _add_action(self):
        name = self.act_name.get().strip()
        if not name:
            return self._set_status("Enter an action name.")
        vals = [v.strip() for v in self.act_vals.get().split(",")]
        if not vals or vals == [""]:
            vals = ["X", ""]
        try:
            self.table.add_action(Action(name=name, possible_values=vals))
            self.act_name.delete(0, tk.END)
            self._refresh_editor()
            self.mark_modified()
        except ValueError as e:
            self._set_status(str(e))

    def _remove_selected_conditions(self):
        sel = self.remove_cond_list.curselection()
        if not sel:
            return self._set_status("Select condition(s) to remove.")
        names = [self.remove_cond_list.get(i) for i in sel]
        for name in names:
            try:
                self.table.remove_condition(name)
            except ValueError:
                pass
        self._refresh_editor()
        self.mark_modified()

    def _remove_selected_actions(self):
        sel = self.remove_act_list.curselection()
        if not sel:
            return self._set_status("Select action(s) to remove.")
        names = [self.remove_act_list.get(i) for i in sel]
        for name in names:
            try:
                self.table.remove_action(name)
            except ValueError:
                pass
        self._refresh_editor()
        self.mark_modified()

    def _remove_selected_rules(self):
        sel = self.remove_rule_list.curselection()
        if not sel:
            return self._set_status("Select rule(s) to remove.")
        # Remove in reverse order so indices don't shift
        for i in sorted(sel, reverse=True):
            try:
                self.table.remove_rule(i)
            except IndexError:
                pass
        self._refresh_editor()
        self.mark_modified()

    def _update_remove_lists(self):
        self.remove_cond_list.delete(0, tk.END)
        for c in self.table.conditions:
            self.remove_cond_list.insert(tk.END, c.name)

        self.remove_act_list.delete(0, tk.END)
        for a in self.table.actions:
            self.remove_act_list.insert(tk.END, a.name)

        self.remove_rule_list.delete(0, tk.END)
        for i, r in enumerate(self.table.rules):
            conds = ", ".join(f"{k}={v}" for k, v in sorted(r.condition_entries.items()) if v != DONT_CARE)
            label = f"R{i+1}"
            if r.is_else:
                label += " ELSE"
            if conds:
                label += f": {conds}"
            self.remove_rule_list.insert(tk.END, label)

    # ══════════════════════════════════════════════
    # Table Grid
    # ══════════════════════════════════════════════

    def _create_table_editor(self, parent):
        frame = tk.Frame(parent, bg=_CLR["bg"])
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.canvas = tk.Canvas(frame, bg="white", highlightthickness=0, bd=0)
        vs = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.canvas.yview)
        hs = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        vs.pack(side=tk.RIGHT, fill=tk.Y)
        hs.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.grid_frame = tk.Frame(self.canvas, bg="white")
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor=tk.NW)
        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._refresh_editor()

    def _refresh_editor(self):
        self._update_remove_lists()
        for w in self.grid_frame.winfo_children():
            w.destroy()

        t = self.table
        if not t.conditions and not t.actions:
            tk.Label(self.grid_frame, text="Add conditions and actions above, then add rules.",
                     fg="#666666", bg="white", font=_FONT).grid(row=0, column=0, padx=30, pady=30)
            return

        pad = dict(padx=0, pady=0, sticky=tk.NSEW)

        # ── Top-left corner ──
        info = t.table_type.value.replace("_", "-")
        if t.constraints:
            info += f"  ({len(t.constraints)} constraints)"
        tk.Label(self.grid_frame, text=info, width=24, anchor=tk.W,
                 bg=_CLR["grid_hdr"], fg=_CLR["grid_hdr_fg"], font=_FONT_GRID,
                 padx=6, pady=4).grid(row=0, column=0, **pad)

        # ── Rule headers ──
        for j, rule in enumerate(t.rules):
            label = f"R{j+1}"
            bg = _CLR["else_hdr"] if rule.is_else else _CLR["grid_hdr"]
            fg = "#333" if rule.is_else else _CLR["grid_hdr_fg"]
            if rule.is_else:
                label += " ELSE"
            if rule.priority != 0:
                label += f" (p{rule.priority})"
            tk.Label(self.grid_frame, text=label, width=10, anchor=tk.CENTER,
                     bg=bg, fg=fg, font=_FONT_GRID_B, pady=4).grid(row=0, column=j+1, **pad)

        # ── Condition rows ──
        row = 1
        for i, cond in enumerate(t.conditions):
            tag = ""
            if cond.is_numeric:
                tag = "  [numeric]"
            elif cond.condition_type == ConditionType.ENUM:
                tag = "  [enum]"
            lbl = tk.Label(self.grid_frame, text=cond.name + tag, width=24, anchor=tk.W,
                           bg=_CLR["cond_hdr"], fg="white", font=_FONT_GRID_B, padx=6, pady=3)
            lbl.grid(row=row, column=0, **pad)
            lbl.bind("<Button-2>", lambda e, n=cond.name: self._remove_condition(n))
            lbl.bind("<Button-3>", lambda e, n=cond.name: self._remove_condition(n))

            for j, rule in enumerate(t.rules):
                val = rule.condition_entries.get(cond.name, DONT_CARE)
                bg = _CLR["else_cell"] if rule.is_else else _CLR["cond_cell"]
                cell = tk.Label(self.grid_frame, text=val, width=10, anchor=tk.CENTER,
                                bg=bg, fg="#1a1a2e", font=_FONT_GRID, cursor="hand2", pady=3)
                cell.grid(row=row, column=j+1, **pad)
                cell.bind("<Button-1>", lambda e, r=i, c=j: self._cycle("condition", r, c))
            row += 1

        # ── Separator ──
        sep = tk.Frame(self.grid_frame, height=2, bg=_CLR["separator"])
        sep.grid(row=row, column=0, columnspan=len(t.rules)+1, sticky=tk.EW)
        row += 1

        # ── Action rows ──
        for i, action in enumerate(t.actions):
            lbl = tk.Label(self.grid_frame, text=action.name, width=24, anchor=tk.W,
                           bg=_CLR["act_hdr"], fg="white", font=_FONT_GRID_B, padx=6, pady=3)
            lbl.grid(row=row, column=0, **pad)
            lbl.bind("<Button-2>", lambda e, n=action.name: self._remove_action(n))
            lbl.bind("<Button-3>", lambda e, n=action.name: self._remove_action(n))

            for j, rule in enumerate(t.rules):
                val = rule.action_entries.get(action.name, "")
                bg = _CLR["else_cell"] if rule.is_else else _CLR["act_cell"]
                display = val if val else "\u2022"
                fg = "#1a1a2e" if val else "#aaa"
                cell = tk.Label(self.grid_frame, text=display, width=10, anchor=tk.CENTER,
                                bg=bg, fg=fg, font=_FONT_GRID, cursor="hand2", pady=3)
                cell.grid(row=row, column=j+1, **pad)
                cell.bind("<Button-1>", lambda e, r=i, c=j: self._cycle("action", r, c))
            row += 1

    def _cycle(self, kind, row_idx, col_idx):
        rule = self.table.rules[col_idx]
        self.table._save_state()
        if kind == "condition":
            cond = self.table.conditions[row_idx]
            cur = rule.condition_entries.get(cond.name, DONT_CARE)
            vals = cond.possible_values + [DONT_CARE]
            try:
                nxt = (vals.index(cur) + 1) % len(vals)
            except ValueError:
                nxt = 0
            rule.condition_entries[cond.name] = vals[nxt]
        else:
            act = self.table.actions[row_idx]
            cur = rule.action_entries.get(act.name, "")
            vals = act.possible_values
            try:
                nxt = (vals.index(cur) + 1) % len(vals)
            except ValueError:
                nxt = 0
            rule.action_entries[act.name] = vals[nxt]
        self._refresh_editor()
        self.mark_modified()

    def _remove_condition(self, name):
        self.table.remove_condition(name)
        self._refresh_editor()
        self.mark_modified()

    def _remove_action(self, name):
        self.table.remove_action(name)
        self._refresh_editor()
        self.mark_modified()

    # ══════════════════════════════════════════════
    # Output Panel
    # ══════════════════════════════════════════════

    def _create_output_panel(self, parent):
        header = tk.Frame(parent, bg=_CLR["bg"])
        header.pack(fill=tk.X, padx=6, pady=(4, 0))
        tk.Label(header, text="Output", font=_FONT_BOLD, bg=_CLR["bg"], fg="#333344").pack(side=tk.LEFT)

        frame = tk.Frame(parent, bg=_CLR["bg"])
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 6))
        self.output = tk.Text(frame, wrap=tk.WORD, font=_FONT_MONO,
                              bg=_CLR["output_bg"], fg=_CLR["output_fg"],
                              insertbackground="#333344",
                              selectbackground="#ccd0da", selectforeground="#1a1a2e",
                              relief=tk.GROOVE, padx=10, pady=8, state=tk.DISABLED, bd=1)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.output.pack(fill=tk.BOTH, expand=True)

    def _show_output(self, text: str):
        self.output.configure(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        self.output.configure(state=tk.DISABLED)

    # ══════════════════════════════════════════════
    # File Operations
    # ══════════════════════════════════════════════

    def new_table(self):
        self.table = DecisionTable()
        self.current_file = None
        self.modified = False
        self._pre_reduce_rules = None
        self._refresh_editor()
        self._update_title()
        self._update_status()

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open Decision Table",
            filetypes=[("All supported", "*.json *.csv *.xlsx"),
                       ("JSON", "*.json"), ("CSV", "*.csv"), ("Excel", "*.xlsx")])
        if not path:
            return
        try:
            self.table = load_file(path)
            self.current_file = path
            self.modified = False
            self._pre_reduce_rules = None
            self._refresh_editor()
            self._update_title()
            self._update_status()
        except Exception as e:
            self._set_status(f"Error: {e}")

    def save_file(self):
        if self.current_file:
            self._do_save(self.current_file)
        else:
            self.save_file_as()

    def save_file_as(self):
        path = filedialog.asksaveasfilename(
            title="Save Decision Table", defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv"), ("Excel", "*.xlsx")])
        if path:
            self._do_save(path)

    def _do_save(self, path):
        try:
            save_file(self.table, path)
            self.current_file = path
            self.modified = False
            self._update_title()
            self._set_status(f"Saved to {path}")
        except Exception as e:
            self._set_status(f"Error saving: {e}")

    def _rename_table(self):
        self._show_output("Enter new table name below and press Enter.")
        entry = ttk.Entry(self.root, font=_FONT)
        entry.insert(0, self.table.name)
        entry.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=3)
        entry.focus_set()
        entry.select_range(0, tk.END)

        def do_rename(e=None):
            name = entry.get().strip()
            if name:
                self.table.name = name
                self.mark_modified()
                self._show_output(f"Table renamed to: {name}")
            entry.destroy()

        entry.bind("<Return>", do_rename)
        entry.bind("<Escape>", lambda e: entry.destroy())

    # ══════════════════════════════════════════════
    # Edit Operations
    # ══════════════════════════════════════════════

    def undo(self):
        if self.table.undo():
            self._refresh_editor()
            self.mark_modified()
            self._set_status("Undo")
        else:
            self._set_status("Nothing to undo.")

    def redo(self):
        if self.table.redo():
            self._refresh_editor()
            self.mark_modified()
            self._set_status("Redo")
        else:
            self._set_status("Nothing to redo.")

    def add_rule(self):
        self.table.add_rule(Rule())
        self._refresh_editor()
        self.mark_modified()

    def add_else_rule(self):
        self.table.add_else_rule()
        self._refresh_editor()
        self.mark_modified()

    def duplicate_last_rule(self):
        if self.table.rules:
            self.table.duplicate_rule(len(self.table.rules) - 1)
            self._refresh_editor()
            self.mark_modified()

    def remove_last_rule(self):
        if self.table.rules:
            self.table.remove_rule(len(self.table.rules) - 1)
            self._refresh_editor()
            self.mark_modified()

    def _move_rule(self, delta):
        if not self.table.rules:
            return
        last = len(self.table.rules) - 1
        self.table.move_rule(last, last + delta)
        self._refresh_editor()
        self.mark_modified()

    # ══════════════════════════════════════════════
    # Constraints
    # ══════════════════════════════════════════════

    def _add_constraint_inline(self, ctype_str):
        if not self.table.conditions:
            return self._set_status("Add conditions first.")
        cond_names = [c.name for c in self.table.conditions]
        self._show_output(
            f"  Adding {ctype_str.upper()} constraint\n\n"
            f"  Available conditions: {', '.join(cond_names)}\n\n"
            f"  Enter as:  ConditionName=Value, ConditionName=Value\n"
            f"  Example:   Age=<18, Coverage=Premium\n\n"
            f"  Type in the entry below and press Enter."
        )
        entry = ttk.Entry(self.root, font=_FONT)
        entry.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=3)
        entry.focus_set()

        def do_add(e=None):
            text = entry.get().strip()
            entry.destroy()
            if not text:
                return
            cond_entries = {}
            for pair in text.split(","):
                key, _, val = pair.partition("=")
                cond_entries[key.strip()] = val.strip()
            self.table.add_constraint(Constraint(
                constraint_type=ConstraintType(ctype_str),
                conditions=cond_entries,
                description=text,
            ))
            self._refresh_editor()
            self.mark_modified()
            self._show_output(f"  Added {ctype_str} constraint: {cond_entries}")

        entry.bind("<Return>", do_add)
        entry.bind("<Escape>", lambda e: entry.destroy())

    def _remove_last_constraint(self):
        if self.table.constraints:
            self.table.remove_constraint(len(self.table.constraints) - 1)
            self._refresh_editor()
            self.mark_modified()
            self._set_status("Removed last constraint.")
        else:
            self._set_status("No constraints to remove.")

    def _list_constraints(self):
        if not self.table.constraints:
            return self._show_output("  No constraints defined.")
        lines = ["  Constraints:", ""]
        for i, c in enumerate(self.table.constraints):
            conds = ", ".join(f"{k}={v}" for k, v in c.conditions.items())
            lines.append(f"  {i+1}. [{c.constraint_type.value.upper()}]  {conds}")
            if c.description:
                lines.append(f"     {c.description}")
            lines.append("")
        self._show_output("\n".join(lines))

    # ══════════════════════════════════════════════
    # Validation
    # ══════════════════════════════════════════════

    def run_validate(self):
        result = validate_all(self.table)
        lines = ["  Validation Results", "  " + "=" * 40, ""]
        for msg in result.messages:
            icon = {"error": "X", "warning": "!", "info": "/"}[msg.severity.value]
            lines.append(f"  [{icon}] [{msg.check}] {msg.message}")
        lines += ["", "  " + "=" * 40]
        lines.append(f"  Result: {'PASSED' if result.is_valid else 'FAILED'}")
        self._show_output("\n".join(lines))
        self._set_status(f"Validation: {len(result.errors)} errors, {len(result.warnings)} warnings")

    # ══════════════════════════════════════════════
    # Reduction
    # ══════════════════════════════════════════════

    def run_reduce(self):
        method = self.reduce_method.get()
        method_map = {
            "Quine-McCluskey": "qm",
            "Petrick": "petrick",
            "Rule Merging": "merge",
            "Espresso": "espresso",
        }
        self._run_reduce_method(method_map.get(method, "qm"))

    def _run_reduce_method(self, method):
        original_rules = self._pre_reduce_rules if self._pre_reduce_rules else list(self.table.rules)
        self._pre_reduce_rules = original_rules
        original_count = len(original_rules)

        methods = {
            "qm": quine_mccluskey,
            "petrick": petricks_method,
            "merge": rule_merging,
            "espresso": espresso,
        }
        res = methods.get(method, quine_mccluskey)(self.table)

        self.table.rules = list(res.reduced_rules)
        self._refresh_editor()
        self.mark_modified()

        cond_names = [c.name for c in self.table.conditions]
        act_names = [a.name for a in self.table.actions]
        lines = [
            f"  {res.method}",
            f"  {original_count} rules  ->  {len(res.reduced_rules)} rules  "
            f"({res.reduction_percentage:.0f}% reduction)",
            "",
            "  ORIGINAL TABLE:",
            self._format_rules_text(cond_names, act_names, original_rules),
            "",
            "  REDUCED TABLE:",
            self._format_rules_text(cond_names, act_names, res.reduced_rules),
        ]
        self._show_output("\n".join(lines))
        self._set_status(f"Reduced: {original_count} -> {len(res.reduced_rules)} rules")

    def undo_reduce(self):
        if self._pre_reduce_rules is None:
            return self._set_status("Nothing to undo.")
        self.table.rules = self._pre_reduce_rules
        self._pre_reduce_rules = None
        self._refresh_editor()
        self.mark_modified()
        self._show_output("  Reduction undone. Original rules restored.")
        self._set_status(f"Restored {len(self.table.rules)} rules")

    def run_compare(self):
        c = compare_reductions(self.table)
        results = [
            ("QM", c.qm_result),
            ("Petrick", c.petrick_result),
            ("Merge", c.rule_merging_result),
            ("Espresso", c.espresso_result),
        ]
        results = [(n, r) for n, r in results if r is not None]

        hdr = f"  {'':20s}" + "".join(f"{n:>12s}" for n, _ in results)
        sep = "  " + "-" * (20 + 12 * len(results))
        lines = [
            "  Reduction Comparison (all 4 methods)",
            "  " + "=" * (20 + 12 * len(results)), "",
            hdr, sep,
            f"  {'Original rules':<20s}" + "".join(f"{len(r.original_rules):>12d}" for _, r in results),
            f"  {'Reduced rules':<20s}" + "".join(f"{len(r.reduced_rules):>12d}" for _, r in results),
            f"  {'Reduction':<20s}" + "".join(f"{r.reduction_percentage:>11.0f}%" for _, r in results),
        ]
        self._show_output("\n".join(lines))
        summary = ", ".join(f"{n}: {len(r.reduced_rules)}" for n, r in results)
        self._set_status(summary)

    def run_equivalence(self):
        if self._pre_reduce_rules is None:
            return self._show_output("  No reduction to compare. Run Reduce first.")
        import copy
        original = copy.deepcopy(self.table)
        original.rules = list(self._pre_reduce_rules)
        is_eq, diffs = original.is_equivalent_to(self.table)
        if is_eq:
            self._show_output("  Tables are EQUIVALENT.\n\n  The reduced table produces identical outputs for all valid inputs.")
        else:
            lines = [f"  Tables DIFFER on {len(diffs)} input(s):", ""]
            for d in diffs[:20]:
                inp = ", ".join(f"{k}={v}" for k, v in sorted(d["input"].items()))
                lines.append(f"  Input: {inp}")
                lines.append(f"    Original: {d['table1_actions']}")
                lines.append(f"    Reduced:  {d['table2_actions']}")
                lines.append("")
            self._show_output("\n".join(lines))

    # ══════════════════════════════════════════════
    # Testing
    # ══════════════════════════════════════════════

    def run_tests(self, test_type):
        generators = {
            "normal": generate_test_cases,
            "boundary": generate_boundary_tests,
            "pairwise": generate_pairwise_tests,
            "all": generate_all_tests,
        }
        tests = generators[test_type](self.table)
        coverage = calculate_coverage(self.table, tests)

        cond_names = [c.name for c in self.table.conditions]
        act_names = [a.name for a in self.table.actions]

        # Auto-size columns based on header + all values
        cond_widths = {}
        for n in cond_names:
            w = len(n)
            for tc in tests:
                w = max(w, len(tc.inputs.get(n, "")))
            cond_widths[n] = w + 2
        act_widths = {}
        for n in act_names:
            w = len(n)
            for tc in tests:
                w = max(w, len(tc.expected_outputs.get(n, "")))
            act_widths[n] = w + 2

        lines = [
            f"  Test Cases ({test_type}):  {len(tests)} tests",
            "",
            f"  {'#':>4s} {'Type':>10s} " +
            "".join(f"{n:>{cond_widths[n]}}" for n in cond_names) +
            "  | " +
            "".join(f"{n:>{act_widths[n]}}" for n in act_names) +
            "  Rules",
            "  " + "-" * (18 + sum(cond_widths.values()) + sum(act_widths.values()) + 10),
        ]

        for i, tc in enumerate(tests, 1):
            cvals = "".join(f"{tc.inputs.get(n, ''):>{cond_widths[n]}}" for n in cond_names)
            avals = "".join(f"{tc.expected_outputs.get(n, ''):>{act_widths[n]}}" for n in act_names)
            rules = ", ".join(f"R{r+1}" for r in tc.covering_rules)
            lines.append(f"  {i:>4d} {tc.test_type:>10s} {cvals}  | {avals}  {rules}")

        lines += ["", "  Coverage:", "  " + coverage.summary().replace("\n", "\n  ")]
        self._show_output("\n".join(lines))
        self._set_status(f"{len(tests)} test cases, {coverage.rule_coverage:.0f}% rule coverage")

    def export_tests(self):
        tests = generate_all_tests(self.table)
        if not tests:
            return self._set_status("No test cases to export.")
        path = filedialog.asksaveasfilename(
            title="Export Test Cases", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")])
        if path:
            export_test_cases_csv(tests, self.table, path)
            self._set_status(f"Exported {len(tests)} test cases to {path}")

    # ══════════════════════════════════════════════
    # Help
    # ══════════════════════════════════════════════

    def _help_quickstart(self):
        self._show_output(
            "  QUICK START GUIDE\n"
            "  =================\n\n"
            "  1. ADD CONDITIONS\n"
            "     Type a name in the Condition field, choose values and type,\n"
            "     then click 'Add Condition'.\n"
            "       - Boolean: T, F  (default)\n"
            "       - Enum: Red, Green, Blue\n"
            "       - Numeric: <18, 18-64, >=65\n\n"
            "  2. ADD ACTIONS\n"
            "     Type a name, set possible values (e.g. 'X, ' for mark/blank),\n"
            "     then click 'Add Action'.\n\n"
            "  3. ADD RULES\n"
            "     Click '+ Rule' in the toolbar. A new column appears in the grid.\n"
            "     Click any cell to cycle through its possible values.\n"
            "     Use '-' for don't-care (matches any value).\n"
            "     Use '+ Else' for a catch-all default rule.\n\n"
            "  4. REMOVING ITEMS\n"
            "     Use the listboxes in the add bar to select one or more\n"
            "     conditions, actions, or rules, then click 'Remove Selected'.\n"
            "     Hold Cmd (Mac) or Ctrl (Windows) to select multiple items.\n\n"
            "  5. CONSTRAINTS\n"
            "     Use the Constraints menu to define impossible combinations,\n"
            "     exclusions, or implications between conditions.\n\n"
            "  6. VALIDATE\n"
            "     Click 'Validate' or press F5 to check for:\n"
            "       - Missing input combinations (completeness)\n"
            "       - Duplicate rules (redundancy)\n"
            "       - Conflicting rules (contradiction)\n"
            "       - Constraint violations\n\n"
            "  7. REDUCE\n"
            "     Select a method (Quine-McCluskey or Petrick) and click\n"
            "     'Reduce' to minimize the table. The output shows the\n"
            "     original vs reduced table for comparison.\n"
            "     Click 'Undo Reduce' to restore the original.\n\n"
            "  8. TEST\n"
            "     Click 'Tests' or press F6 to generate test cases.\n"
            "     Includes per-rule, boundary value, and pairwise tests\n"
            "     with coverage metrics.\n"
            "     Use Testing > Export Tests to CSV to save them.\n\n"
            "  9. SAVE\n"
            "     Ctrl+S to save. Supports JSON, CSV, and Excel formats.\n"
            "     All features (constraints, priorities, else rules,\n"
            "     condition types) are preserved across all formats."
        )

    def _help_shortcuts(self):
        self._show_output(
            "  KEYBOARD SHORTCUTS\n"
            "  ==================\n\n"
            "  File:\n"
            "    Ctrl+N          New table\n"
            "    Ctrl+O          Open file\n"
            "    Ctrl+S          Save\n"
            "    Ctrl+Q          Quit\n\n"
            "  Edit:\n"
            "    Ctrl+Z          Undo\n"
            "    Ctrl+Y          Redo\n\n"
            "  Analysis:\n"
            "    F5              Validate all\n"
            "    F6              Generate all tests\n\n"
            "  Grid:\n"
            "    Left-click      Cycle cell value\n"
            "    Right-click     Remove condition/action (on row header)\n\n"
            "  Remove Lists:\n"
            "    Click           Select one item\n"
            "    Cmd/Ctrl+click  Select multiple items\n"
            "    Shift+click     Select range of items"
        )

    def _help_condition_types(self):
        self._show_output(
            "  CONDITION TYPES\n"
            "  ===============\n\n"
            "  BOOLEAN (default)\n"
            "    Values: T (true), F (false)\n"
            "    Example: 'Is Member', 'Has License'\n\n"
            "  ENUM\n"
            "    Custom discrete values.\n"
            "    Example: Color with values 'Red, Green, Blue'\n"
            "    Example: Status with values 'Active, Suspended, Closed'\n\n"
            "  NUMERIC\n"
            "    Range-based partitions with automatic boundary value extraction.\n"
            "    Syntax:\n"
            "      <N         less than N\n"
            "      <=N        less than or equal to N\n"
            "      >N         greater than N\n"
            "      >=N        greater than or equal to N\n"
            "      A-B        from A (inclusive) to B (exclusive)\n\n"
            "    Example: Age with ranges '<18, 18-64, >=65'\n"
            "    Example: Score with ranges '<60, 60-79, 80-89, >=90'\n\n"
            "    Boundary value tests are auto-generated at range edges."
        )

    def _help_constraint_types(self):
        self._show_output(
            "  CONSTRAINT TYPES\n"
            "  ================\n\n"
            "  IMPOSSIBLE\n"
            "    This combination of values can never occur.\n"
            "    Example: Age=<18, Coverage=Premium\n"
            "    (Minors cannot apply for premium coverage.)\n\n"
            "  EXCLUSION\n"
            "    These values are mutually exclusive (cannot be true together).\n"
            "    Example: Status=Active, Status=Closed\n\n"
            "  IMPLICATION\n"
            "    If the first condition has this value, the second must too.\n"
            "    The first pair is the 'if', the second is the 'then'.\n"
            "    Example: Age=<18, Smoker=F\n"
            "    (If under 18, then must be non-smoker.)\n\n"
            "  EFFECTS:\n"
            "    - Validation skips constrained combinations\n"
            "    - Reduction treats them as don't-cares\n"
            "    - Test generation avoids them"
        )

    def _help_reduction(self):
        self._show_output(
            "  REDUCTION ALGORITHMS (4 methods)\n"
            "  ================================\n\n"
            "  QUINE-McCLUSKEY\n"
            "    A systematic method to find the minimum set of rules.\n"
            "    1. Groups rules by their action outputs\n"
            "    2. Encodes conditions as binary minterms\n"
            "    3. Iteratively combines minterms differing by 1 bit\n"
            "    4. Collects prime implicants (cannot be further combined)\n"
            "    5. Uses greedy selection starting with essential PIs\n"
            "    Best for: small-medium tables, educational use.\n\n"
            "  PETRICK'S METHOD\n"
            "    Builds on Quine-McCluskey but finds ALL minimal covers.\n"
            "    After finding prime implicants:\n"
            "    1. Identifies essential PIs (must be included)\n"
            "    2. Builds product-of-sums for remaining coverage\n"
            "    3. Expands to find every possible minimal cover\n"
            "    4. Selects the smallest one\n"
            "    Best for: guaranteed optimal result. Slower on large tables.\n\n"
            "  RULE MERGING\n"
            "    The most intuitive algorithm. Scans pairs of rules:\n"
            "    - If two rules have the same actions and differ in exactly\n"
            "      one condition, and together cover all values of that\n"
            "      condition, they merge into one rule with don't-care.\n"
            "    - Repeats until no more merges are possible.\n"
            "    Works directly on the table (no binary encoding) so it\n"
            "    handles multi-valued conditions naturally.\n"
            "    Best for: understanding reduction step by step.\n\n"
            "  ESPRESSO\n"
            "    Industry-standard heuristic (UC Berkeley, used in chip design).\n"
            "    Three iterative operations:\n"
            "    1. EXPAND: Generalize each rule (add don't-cares) without\n"
            "       covering inputs assigned to different actions.\n"
            "    2. IRREDUNDANT: Remove rules fully covered by others.\n"
            "    3. REDUCE: Make rules more specific to create new\n"
            "       expansion opportunities in the next iteration.\n"
            "    Repeats until stable. Near-optimal, much faster than\n"
            "    Petrick on large tables.\n"
            "    Best for: large tables, production use.\n\n"
            "  MULTI-VALUED CONDITIONS:\n"
            "    All methods support enum/numeric conditions.\n"
            "    QM/Petrick use one-hot binary encoding with post-processing\n"
            "    to collapse back to don't-cares. Rule Merging and Espresso\n"
            "    work directly on the table representation.\n\n"
            "  Use 'Compare All Methods' to run all 4 side by side."
        )

    def _help_testing(self):
        self._show_output(
            "  TEST GENERATION\n"
            "  ===============\n\n"
            "  NORMAL (per-rule)\n"
            "    Generates one test case per rule, ensuring every rule\n"
            "    is exercised at least once. Picks a valid input combination\n"
            "    that satisfies each rule's conditions.\n\n"
            "  BOUNDARY VALUE ANALYSIS (BVA)\n"
            "    For numeric conditions, generates test cases at:\n"
            "      - Just below each boundary (e.g., 17 for '<18')\n"
            "      - At the boundary (e.g., 18)\n"
            "      - Just above (e.g., 19)\n"
            "    These are the values most likely to expose off-by-one bugs.\n\n"
            "  PAIRWISE\n"
            "    Generates the smallest set of test cases that covers\n"
            "    every pair of condition values at least once.\n"
            "    Uses a greedy algorithm to minimize test count.\n\n"
            "  ALL\n"
            "    Combines normal + boundary + pairwise, deduplicated.\n\n"
            "  COVERAGE METRICS:\n"
            "    - Rule coverage: % of rules exercised\n"
            "    - Condition value coverage: which values tested\n"
            "    - Action value coverage: which outputs observed"
        )

    def _show_about(self):
        self._show_output(
            "  Decision Table Editor  v0.2.0\n"
            "  =============================\n\n"
            "  A tool for creation, editing, validation, optimization,\n"
            "  and test generation for decision tables.\n\n"
            "  Designed for software development students learning\n"
            "  requirements management, development, and testing.\n\n"
            "  Features:\n"
            "    - Boolean, enum, and numeric conditions\n"
            "    - Constraints (exclusion, implication, impossible)\n"
            "    - Else rules and rule priority\n"
            "    - Single-hit and multi-hit table types\n"
            "    - Validation (5 checks, constraint-aware)\n"
            "    - Reduction (Quine-McCluskey, Petrick's Method)\n"
            "    - Test generation (normal, BVA, pairwise)\n"
            "    - Coverage metrics\n"
            "    - JSON, CSV, Excel import/export\n"
            "    - Full undo/redo (50 levels)\n\n"
            "  DISCLAIMER\n"
            "  ----------\n"
            "  This software is provided for research and educational\n"
            "  purposes only. It is provided \"as is\" without warranty\n"
            "  of any kind, express or implied. The authors and\n"
            "  contributors assume no responsibility or liability for\n"
            "  any errors, omissions, or damages arising from the use\n"
            "  of this software. Use at your own risk.\n\n"
            "  Licensed under the MIT License.\n"
        )

    # ══════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════

    def _format_rules_text(self, cond_names, act_names, rules):
        if not rules:
            return "    (no rules)"

        # Auto-size: find widest value in each column
        col_widths = []
        for i, r in enumerate(rules):
            w = len(f"R{i+1}")
            for n in cond_names:
                w = max(w, len(r.condition_entries.get(n, DONT_CARE)))
            for n in act_names:
                w = max(w, len(r.action_entries.get(n, "")))
            col_widths.append(w + 2)  # padding

        name_w = max(len(n) for n in cond_names + act_names) + 2

        hdr = "  " + " " * name_w + "".join(f"{'R' + str(i+1):>{col_widths[i]}}" for i in range(len(rules)))
        sep = "  " + " " * name_w + "-" * sum(col_widths)
        lines = [hdr, sep]
        for n in cond_names:
            row = "  " + f"{n:<{name_w}}"
            for i, r in enumerate(rules):
                row += f"{r.condition_entries.get(n, DONT_CARE):>{col_widths[i]}}"
            lines.append(row)
        lines.append(sep)
        for n in act_names:
            row = "  " + f"{n:<{name_w}}"
            for i, r in enumerate(rules):
                row += f"{r.action_entries.get(n, ''):>{col_widths[i]}}"
            lines.append(row)
        return "\n".join(lines)

    def _set_status(self, text):
        self.status_var.set(text)

    def _update_title(self):
        name = self.table.name or "Untitled"
        f = f" - {self.current_file}" if self.current_file else ""
        m = " *" if self.modified else ""
        self.root.title(f"Decision Table Editor - {name}{f}{m}")

    def _update_status(self):
        parts = [
            f"{len(self.table.conditions)} conditions",
            f"{len(self.table.actions)} actions",
            f"{len(self.table.rules)} rules",
        ]
        if self.table.constraints:
            parts.append(f"{len(self.table.constraints)} constraints")
        parts.append(self.table.table_type.value.replace("_", "-"))
        self._set_status("  |  ".join(parts))

    def mark_modified(self):
        self.modified = True
        self._update_title()
        self._update_status()

    def run(self):
        self.root.mainloop()


def main():
    app = DecisionTableApp()
    app.run()


if __name__ == "__main__":
    main()
