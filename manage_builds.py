import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, BuildType, BuildVersion


class BuildManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Správa stažených buildů")

        # Dropdown pro BuildType
        self.type_var = tk.StringVar()
        self.type_dropdown = ttk.Combobox(root, textvariable=self.type_var, state="readonly")
        self.type_dropdown.pack(fill="x", padx=10, pady=5)
        self.type_dropdown.bind("<<ComboboxSelected>>", lambda e: self.refresh_builds())  # 🔑

        # Seznam buildů
        self.tree = ttk.Treeview(root, columns=("mc_version", "build_number", "file_path"), show="headings")
        self.tree.heading("mc_version", text="MC verze")
        self.tree.heading("build_number", text="Build číslo")
        self.tree.heading("file_path", text="Cesta k souboru")
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

        # Tlačítka
        frame = tk.Frame(root)
        frame.pack(fill="x", padx=10, pady=5)

        tk.Button(frame, text="Obnovit", command=self.refresh_builds).pack(side="left", padx=5)
        tk.Button(frame, text="Smazat vybraný", command=self.delete_selected).pack(side="left", padx=5)
        tk.Button(frame, text="Smazat všechny tohoto typu", command=self.delete_all_of_type).pack(side="left", padx=5)
        tk.Button(frame, text="Smazat všechny buildy", command=self.delete_all).pack(side="left", padx=5)

        # Načti typy buildů
        with app.app_context():
            types = BuildType.query.all()
            self.type_dropdown["values"] = [t.name for t in types]
            if types:
                self.type_var.set(types[0].name)

        self.refresh_builds()

    def refresh_builds(self):
        """Načti seznam buildů pro vybraný BuildType"""
        self.tree.delete(*self.tree.get_children())
        selected_type = self.type_var.get()
        if not selected_type:
            return

        with app.app_context():
            build_type = BuildType.query.filter_by(name=selected_type).first()
            if not build_type:
                return
            builds = BuildVersion.query.filter_by(build_type=build_type).all()

            for b in builds:
                self.tree.insert("", "end", iid=b.id, values=(b.mc_version, b.build_number, b.file_path))

    def delete_selected(self):
        """Smazat vybraný build"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Upozornění", "Musíte vybrat build k odstranění.")
            return

        build_id = int(selected[0])
        with app.app_context():
            build = BuildVersion.query.get(build_id)
            if build:
                db.session.delete(build)
                db.session.commit()
                messagebox.showinfo("Hotovo", f"Build {build.mc_version}-{build.build_number} byl odstraněn.")
        self.refresh_builds()

    def delete_all_of_type(self):
        """Smazat všechny buildy vybraného typu"""
        selected_type = self.type_var.get()
        if not selected_type:
            return

        if not messagebox.askyesno("Potvrzení", f"Opravdu chcete smazat všechny buildy typu {selected_type}?"):
            return

        with app.app_context():
            build_type = BuildType.query.filter_by(name=selected_type).first()
            if build_type:
                BuildVersion.query.filter_by(build_type=build_type).delete()
                db.session.commit()
        self.refresh_builds()

    def delete_all(self):
        """Smazat všechny buildy v databázi"""
        if not messagebox.askyesno("Potvrzení", "Opravdu chcete smazat všechny buildy (všechny typy)?"):
            return

        with app.app_context():
            BuildVersion.query.delete()
            db.session.commit()
        self.refresh_builds()


if __name__ == "__main__":
    root = tk.Tk()
    gui = BuildManagerGUI(root)
    root.mainloop()
