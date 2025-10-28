"""GUI utility for managing trip page and snippet data."""

from __future__ import annotations

import argparse
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, Optional

from . import generator

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - import guard
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

LOGGER = logging.getLogger(__name__)

PAGE_FIELDS = [
    ("page_id", "Page ID"),
    ("page_name", "Name"),
    ("page_desc", "Description"),
]

SNIPPET_FIELDS = [
    ("snippet_id", "Snippet ID"),
    ("page_id", "Page ID"),
    ("code", "Code"),
    ("request_desc", "Request"),
    ("destination", "Destination"),
    ("image", "Image"),
    ("imagetitle", "Image Title"),
    ("tagline1", "Tagline 1"),
    ("tagline2", "Tagline 2"),
    ("price", "Price"),
    ("title", "Title"),
    ("shortdesc", "Short Description"),
    ("description", "Description"),
    ("inclusionhtml", "Inclusion HTML"),
    ("active", "Active"),
]


class TripManagerApp:
    """Tkinter application for managing trip pages and snippets."""

    def __init__(self, master: tk.Tk, connection: "psycopg.Connection"):
        self.master = master
        self.conn = connection
        self.master.title("Trip Manager")

        self.page_entries: Dict[str, tk.Entry] = {}
        self.snippet_entries: Dict[str, tk.Entry] = {}

        self.current_page_id: Optional[int] = None
        self.current_snippet_id: Optional[int] = None

        self._build_widgets()
        self._load_pages()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        container = ttk.Frame(self.master, padding=10)
        container.grid(row=0, column=0, sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        # Master pane
        master_frame = ttk.LabelFrame(container, text="Trip Pages")
        master_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.page_tree = ttk.Treeview(
            master_frame,
            columns=("page_name", "page_desc"),
            show="headings",
            selectmode="browse",
            height=10,
        )
        self.page_tree.heading("page_name", text="Name")
        self.page_tree.heading("page_desc", text="Description")
        self.page_tree.column("page_name", width=180)
        self.page_tree.column("page_desc", width=280)
        self.page_tree.bind("<<TreeviewSelect>>", self._on_page_select)
        self.page_tree.grid(row=0, column=0, sticky="nsew")
        master_frame.columnconfigure(0, weight=1)
        master_frame.rowconfigure(0, weight=1)

        page_form = ttk.Frame(master_frame, padding=(0, 10, 0, 0))
        page_form.grid(row=1, column=0, sticky="ew")

        for idx, (field, label_text) in enumerate(PAGE_FIELDS):
            ttk.Label(page_form, text=label_text).grid(row=idx, column=0, sticky="w")
            entry = ttk.Entry(page_form, width=40)
            entry.grid(row=idx, column=1, sticky="ew", padx=(5, 0))
            page_form.rowconfigure(idx, weight=0)
            self.page_entries[field] = entry
        page_form.columnconfigure(1, weight=1)

        page_button_bar = ttk.Frame(master_frame, padding=(0, 5))
        page_button_bar.grid(row=2, column=0, sticky="ew")
        ttk.Button(page_button_bar, text="Add Page", command=self._add_page).grid(
            row=0, column=0, padx=(0, 5)
        )
        ttk.Button(page_button_bar, text="Save Page", command=self._save_page).grid(
            row=0, column=1
        )

        # Detail pane
        detail_frame = ttk.LabelFrame(container, text="Trip Snippets")
        detail_frame.grid(row=0, column=1, sticky="nsew")
        container.columnconfigure(1, weight=1)

        self.snippet_tree = ttk.Treeview(
            detail_frame,
            columns=("code", "title", "active"),
            show="headings",
            selectmode="browse",
            height=10,
        )
        self.snippet_tree.heading("code", text="Code")
        self.snippet_tree.heading("title", text="Title")
        self.snippet_tree.heading("active", text="Active")
        self.snippet_tree.column("code", width=90)
        self.snippet_tree.column("title", width=200)
        self.snippet_tree.column("active", width=60, anchor="center")
        self.snippet_tree.bind("<<TreeviewSelect>>", self._on_snippet_select)
        self.snippet_tree.grid(row=0, column=0, sticky="nsew")
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)

        snippet_form = ttk.Frame(detail_frame, padding=(0, 10, 0, 0))
        snippet_form.grid(row=1, column=0, sticky="ew")

        for idx, (field, label_text) in enumerate(SNIPPET_FIELDS):
            ttk.Label(snippet_form, text=label_text).grid(row=idx, column=0, sticky="w")
            entry = ttk.Entry(snippet_form, width=40)
            entry.grid(row=idx, column=1, sticky="ew", padx=(5, 0))
            snippet_form.rowconfigure(idx, weight=0)
            self.snippet_entries[field] = entry
            if field == "page_id":
                entry.configure(state="disabled")
        snippet_form.columnconfigure(1, weight=1)

        snippet_button_bar = ttk.Frame(detail_frame, padding=(0, 5))
        snippet_button_bar.grid(row=2, column=0, sticky="ew")
        ttk.Button(snippet_button_bar, text="Add Snippet", command=self._add_snippet).grid(
            row=0, column=0, padx=(0, 5)
        )
        ttk.Button(snippet_button_bar, text="Save Snippet", command=self._save_snippet).grid(
            row=0, column=1
        )

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------
    def _load_pages(self) -> None:
        self.page_tree.delete(*self.page_tree.get_children())
        with self.conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT page_id, page_name, page_desc FROM tlinq.trip_page ORDER BY page_id")
            for row in cursor.fetchall():
                self.page_tree.insert(
                    "",
                    tk.END,
                    iid=str(row["page_id"]),
                    values=(row["page_name"], row["page_desc"] or ""),
                )
        LOGGER.info("Loaded trip pages")

    def _load_snippets(self, page_id: int) -> None:
        self.snippet_tree.delete(*self.snippet_tree.get_children())
        with self.conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT snippet_id, code, title, active FROM tlinq.trip_snippet WHERE page_id = %s ORDER BY snippet_id",
                (page_id,),
            )
            for row in cursor.fetchall():
                self.snippet_tree.insert(
                    "",
                    tk.END,
                    iid=str(row["snippet_id"]),
                    values=(row["code"], row["title"] or "", row["active"]),
                )
        LOGGER.info("Loaded snippets for page_id=%s", page_id)

    # ------------------------------------------------------------------
    # Selection callbacks
    # ------------------------------------------------------------------
    def _on_page_select(self, event) -> None:  # pragma: no cover - UI callback
        selected = self.page_tree.selection()
        if not selected:
            return
        page_id = int(selected[0])
        self.current_page_id = page_id
        self.current_snippet_id = None
        self._populate_page_form(page_id)
        self._load_snippets(page_id)
        self._clear_snippet_form()

    def _on_snippet_select(self, event) -> None:  # pragma: no cover - UI callback
        selected = self.snippet_tree.selection()
        if not selected:
            return
        snippet_id = int(selected[0])
        self.current_snippet_id = snippet_id
        self._populate_snippet_form(snippet_id)

    # ------------------------------------------------------------------
    # Form helpers
    # ------------------------------------------------------------------
    def _populate_page_form(self, page_id: int) -> None:
        with self.conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT page_id, page_name, page_desc FROM tlinq.trip_page WHERE page_id = %s",
                (page_id,),
            )
            row = cursor.fetchone()
        if not row:
            return
        for field, _ in PAGE_FIELDS:
            entry = self.page_entries[field]
            entry.configure(state="normal")
            entry.delete(0, tk.END)
            value = row.get(field) or ""
            entry.insert(0, value)
            if field == "page_id":
                entry.configure(state="disabled")

    def _populate_snippet_form(self, snippet_id: int) -> None:
        with self.conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT * FROM tlinq.trip_snippet WHERE snippet_id = %s", (snippet_id,))
            row = cursor.fetchone()
        if not row:
            return
        for field, _ in SNIPPET_FIELDS:
            entry = self.snippet_entries[field]
            entry.configure(state="normal")
            entry.delete(0, tk.END)
            value = row.get(field)
            if value is None:
                value = ""
            entry.insert(0, value)
            if field in {"snippet_id", "page_id"}:
                entry.configure(state="disabled")

    def _clear_page_form(self) -> None:
        for field, entry in self.page_entries.items():
            entry.configure(state="normal")
            entry.delete(0, tk.END)
        self.current_page_id = None

    def _clear_snippet_form(self) -> None:
        for field, entry in self.snippet_entries.items():
            entry.configure(state="normal")
            entry.delete(0, tk.END)
        self.current_snippet_id = None
        page_entry = self.snippet_entries.get("page_id")
        if page_entry is not None:
            page_entry.configure(state="normal")
            if self.current_page_id is not None:
                page_entry.insert(0, str(self.current_page_id))
            page_entry.configure(state="disabled")

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------
    def _add_page(self) -> None:  # pragma: no cover - UI callback
        self._clear_page_form()

    def _save_page(self) -> None:  # pragma: no cover - UI callback
        data = {field: entry.get().strip() for field, entry in self.page_entries.items()}
        if not data["page_id"]:
            messagebox.showerror("Validation Error", "Page ID is required.")
            return
        if not data["page_name"]:
            messagebox.showerror("Validation Error", "Page name is required.")
            return
        try:
            page_id = int(data["page_id"])
        except ValueError:
            messagebox.showerror("Validation Error", "Page ID must be an integer.")
            return

        try:
            with self.conn.cursor() as cursor:
                if self.current_page_id is None:
                    cursor.execute(
                        "INSERT INTO tlinq.trip_page (page_id, page_name, page_desc) VALUES (%s, %s, %s)",
                        (page_id, data["page_name"], data.get("page_desc") or None),
                    )
                    LOGGER.info("Inserted trip_page %s", page_id)
                else:
                    cursor.execute(
                        "UPDATE tlinq.trip_page SET page_name = %s, page_desc = %s WHERE page_id = %s",
                        (data["page_name"], data.get("page_desc") or None, self.current_page_id),
                    )
                    LOGGER.info("Updated trip_page %s", self.current_page_id)
            self.conn.commit()
        except Exception as exc:  # pragma: no cover - UI callback
            self.conn.rollback()
            LOGGER.exception("Failed to save page")
            messagebox.showerror("Database Error", str(exc))
            return

        self._load_pages()
        self.page_tree.selection_set(str(page_id))
        self.page_tree.focus(str(page_id))
        messagebox.showinfo("Success", "Page saved successfully.")

    def _add_snippet(self) -> None:  # pragma: no cover - UI callback
        if self.current_page_id is None:
            messagebox.showwarning("Select Page", "Select a page before adding snippets.")
            return
        self._clear_snippet_form()

    def _save_snippet(self) -> None:  # pragma: no cover - UI callback
        if self.current_page_id is None:
            messagebox.showwarning("Select Page", "Select a page before saving snippets.")
            return
        data = {field: entry.get().strip() for field, entry in self.snippet_entries.items()}
        if not data["snippet_id"]:
            messagebox.showerror("Validation Error", "Snippet ID is required.")
            return
        try:
            snippet_id = int(data["snippet_id"])
        except ValueError:
            messagebox.showerror("Validation Error", "Snippet ID must be an integer.")
            return

        active_value = data.get("active", "")
        if active_value:
            try:
                active_int = int(active_value)
            except ValueError:
                messagebox.showerror("Validation Error", "Active must be an integer.")
                return
        else:
            active_int = 0

        def _normalize(value: str) -> Optional[str]:
            return value if value else None

        try:
            with self.conn.cursor() as cursor:
                if self.current_snippet_id is None:
                    cursor.execute(
                        """
                        INSERT INTO tlinq.trip_snippet (
                            snippet_id, page_id, code, request_desc, destination, image, imagetitle,
                            tagline1, tagline2, price, title, shortdesc, description, inclusionhtml, active
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            snippet_id,
                            self.current_page_id,
                            _normalize(data.get("code", "")),
                            _normalize(data.get("request_desc", "")),
                            _normalize(data.get("destination", "")),
                            _normalize(data.get("image", "")),
                            _normalize(data.get("imagetitle", "")),
                            _normalize(data.get("tagline1", "")),
                            _normalize(data.get("tagline2", "")),
                            _normalize(data.get("price", "")),
                            _normalize(data.get("title", "")),
                            _normalize(data.get("shortdesc", "")),
                            _normalize(data.get("description", "")),
                            _normalize(data.get("inclusionhtml", "")),
                            active_int,
                        ),
                    )
                    LOGGER.info("Inserted trip_snippet %s", snippet_id)
                else:
                    cursor.execute(
                        """
                        UPDATE tlinq.trip_snippet SET
                            code = %s,
                            request_desc = %s,
                            destination = %s,
                            image = %s,
                            imagetitle = %s,
                            tagline1 = %s,
                            tagline2 = %s,
                            price = %s,
                            title = %s,
                            shortdesc = %s,
                            description = %s,
                            inclusionhtml = %s,
                            active = %s
                        WHERE snippet_id = %s
                        """,
                        (
                            _normalize(data.get("code", "")),
                            _normalize(data.get("request_desc", "")),
                            _normalize(data.get("destination", "")),
                            _normalize(data.get("image", "")),
                            _normalize(data.get("imagetitle", "")),
                            _normalize(data.get("tagline1", "")),
                            _normalize(data.get("tagline2", "")),
                            _normalize(data.get("price", "")),
                            _normalize(data.get("title", "")),
                            _normalize(data.get("shortdesc", "")),
                            _normalize(data.get("description", "")),
                            _normalize(data.get("inclusionhtml", "")),
                            active_int,
                            self.current_snippet_id,
                        ),
                    )
                    LOGGER.info("Updated trip_snippet %s", self.current_snippet_id)
            self.conn.commit()
        except Exception as exc:  # pragma: no cover - UI callback
            self.conn.rollback()
            LOGGER.exception("Failed to save snippet")
            messagebox.showerror("Database Error", str(exc))
            return

        self.current_snippet_id = snippet_id
        self._load_snippets(self.current_page_id)
        self.snippet_tree.selection_set(str(snippet_id))
        self.snippet_tree.focus(str(snippet_id))
        messagebox.showinfo("Success", "Snippet saved successfully.")

    # ------------------------------------------------------------------
    # Shutdown helper
    # ------------------------------------------------------------------
    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # pragma: no cover - cleanup guard
            LOGGER.exception("Error while closing database connection")


def _init_connection() -> "psycopg.Connection":
    if psycopg is None:  # pragma: no cover - environment specific branch
        raise RuntimeError(
            "psycopg is required for the GUI manager. Install it before running the application."
        ) from _IMPORT_ERROR
    config = generator.load_db_config()
    conn = generator.connect_to_db(config)
    conn.autocommit = False
    return conn


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Manage trip pages and snippets via GUI")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    try:
        conn = _init_connection()
    except Exception as exc:  # pragma: no cover - start-up failure
        LOGGER.exception("Unable to initialise database connection")
        raise SystemExit(str(exc)) from exc
    root = tk.Tk()
    app = TripManagerApp(root, conn)

    def on_close() -> None:
        app.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
