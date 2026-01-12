#!/usr/bin/env python3
"""
OpenShift ImageSetConfiguration Generator - GUI

A graphical user interface for the OpenShift ImageSetConfiguration generator.
This GUI provides an easy way to configure and generate ImageSetConfiguration files
without using command-line arguments.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
from typing import Dict, List, Any
import threading
import subprocess
from ..generator import ImageSetGenerator


class ImageSetGeneratorGUI:
    """GUI for the OpenShift ImageSetConfiguration Generator"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenShift ImageSetConfiguration Generator")
        self.root.geometry("900x700")
        
        # Variables for form data
        self.ocp_versions_var = tk.StringVar()
        self.ocp_channel_var = tk.StringVar(value="stable-4.14")
        self.operators_var = tk.StringVar()
        self.operator_catalog_var = tk.StringVar(value="registry.redhat.io/redhat/redhat-operator-index")
        self.additional_images_var = tk.StringVar()
        self.output_file_var = tk.StringVar(value="imageset-config.yaml")
        
        # Helm charts data
        self.helm_charts = []
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Basic Configuration Tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Basic Configuration")
        self.setup_basic_tab(basic_frame)
        
        # Advanced Configuration Tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="Advanced")
        self.setup_advanced_tab(advanced_frame)
        
        # Preview Tab
        preview_frame = ttk.Frame(notebook)
        notebook.add(preview_frame, text="Preview & Generate")
        self.setup_preview_tab(preview_frame)
        
    def setup_basic_tab(self, parent):
        """Setup the basic configuration tab"""
        # Main container with scrollbar
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # OCP Versions Section
        ocp_section = ttk.LabelFrame(scrollable_frame, text="OpenShift Platform Versions", padding=10)
        ocp_section.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(ocp_section, text="OCP Versions (comma-separated):").pack(anchor="w")
        ttk.Entry(ocp_section, textvariable=self.ocp_versions_var, width=60).pack(fill="x", pady=2)
        ttk.Label(ocp_section, text="Example: 4.14.1,4.14.2,4.14.3", font=("Arial", 8)).pack(anchor="w")
        
        ttk.Label(ocp_section, text="OCP Channel:").pack(anchor="w", pady=(10, 0))
        channel_frame = ttk.Frame(ocp_section)
        channel_frame.pack(fill="x", pady=2)
        
        channels = ["stable-4.12", "stable-4.13", "stable-4.14", "stable-4.15", "fast-4.14", "candidate-4.14"]
        channel_combo = ttk.Combobox(channel_frame, textvariable=self.ocp_channel_var, values=channels, width=30)
        channel_combo.pack(side="left")
        
        # Operators Section
        ops_section = ttk.LabelFrame(scrollable_frame, text="Operators", padding=10)
        ops_section.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(ops_section, text="Operators (comma-separated suggestions):").pack(anchor="w")
        ttk.Entry(ops_section, textvariable=self.operators_var, width=60).pack(fill="x", pady=2)
        ttk.Label(ops_section, text="Example: logging,monitoring,pipelines,service-mesh", font=("Arial", 8)).pack(anchor="w")
        
        # Common operators checkboxes
        ttk.Label(ops_section, text="Common Operators (click to add):").pack(anchor="w", pady=(10, 0))
        
        operators_frame = ttk.Frame(ops_section)
        operators_frame.pack(fill="x", pady=5)
        
        common_operators = [
            ("Logging", "logging"),
            ("Monitoring", "monitoring"),
            ("Pipelines", "pipelines"),
            ("GitOps", "gitops"),
            ("Service Mesh", "service-mesh"),
            ("Serverless", "serverless"),
            ("Storage (ODF)", "storage"),
            ("Elasticsearch", "elasticsearch"),
            ("Jaeger", "jaeger")
        ]
        
        for i, (display_name, op_name) in enumerate(common_operators):
            btn = ttk.Button(operators_frame, text=display_name, 
                           command=lambda op=op_name: self.add_operator(op))
            btn.grid(row=i//3, column=i%3, padx=5, pady=2, sticky="ew")
        
        # Configure grid weights
        for i in range(3):
            operators_frame.columnconfigure(i, weight=1)
        
        # Operator Catalog
        ttk.Label(ops_section, text="Operator Catalog:").pack(anchor="w", pady=(10, 0))
        ttk.Entry(ops_section, textvariable=self.operator_catalog_var, width=60).pack(fill="x", pady=2)
        
        # Output Section
        output_section = ttk.LabelFrame(scrollable_frame, text="Output Configuration", padding=10)
        output_section.pack(fill="x", padx=10, pady=5)
        
        output_frame = ttk.Frame(output_section)
        output_frame.pack(fill="x")
        
        ttk.Label(output_frame, text="Output File:").pack(side="left")
        ttk.Entry(output_frame, textvariable=self.output_file_var, width=40).pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(output_frame, text="Browse", command=self.browse_output_file).pack(side="right")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def setup_advanced_tab(self, parent):
        """Setup the advanced configuration tab"""
        # Additional Images Section
        images_section = ttk.LabelFrame(parent, text="Additional Images", padding=10)
        images_section.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(images_section, text="Additional Container Images (comma-separated):").pack(anchor="w")
        ttk.Entry(images_section, textvariable=self.additional_images_var, width=60).pack(fill="x", pady=2)
        ttk.Label(images_section, text="Example: registry.redhat.io/ubi8/ubi:latest,quay.io/my-org/app:v1.0", 
                 font=("Arial", 8)).pack(anchor="w")
        
        # Helm Charts Section
        helm_section = ttk.LabelFrame(parent, text="Helm Charts", padding=10)
        helm_section.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Helm charts controls
        helm_controls = ttk.Frame(helm_section)
        helm_controls.pack(fill="x", pady=5)
        
        ttk.Button(helm_controls, text="Add Helm Chart", command=self.add_helm_chart).pack(side="left")
        ttk.Button(helm_controls, text="Remove Selected", command=self.remove_helm_chart).pack(side="left", padx=5)
        
        # Helm charts list
        self.helm_tree = ttk.Treeview(helm_section, columns=("name", "repository", "version"), show="headings", height=8)
        self.helm_tree.heading("name", text="Chart Name")
        self.helm_tree.heading("repository", text="Repository")
        self.helm_tree.heading("version", text="Version")
        
        self.helm_tree.column("name", width=200)
        self.helm_tree.column("repository", width=300)
        self.helm_tree.column("version", width=100)
        
        # Scrollbar for helm tree
        helm_scroll = ttk.Scrollbar(helm_section, orient="vertical", command=self.helm_tree.yview)
        self.helm_tree.configure(yscrollcommand=helm_scroll.set)
        
        self.helm_tree.pack(side="left", fill="both", expand=True)
        helm_scroll.pack(side="right", fill="y")
        
    def setup_preview_tab(self, parent):
        """Setup the preview and generate tab"""
        # Controls
        controls_frame = ttk.Frame(parent)
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(controls_frame, text="Generate Preview", command=self.generate_preview).pack(side="left")
        ttk.Button(controls_frame, text="Generate & Save", command=self.generate_and_save).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Clear Preview", command=self.clear_preview).pack(side="left", padx=5)
        
        # Preview area
        preview_frame = ttk.LabelFrame(parent, text="Generated YAML Preview", padding=5)
        preview_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=25, width=80)
        self.preview_text.pack(fill="both", expand=True)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(parent, textvariable=self.status_var, relief="sunken")
        status_bar.pack(side="bottom", fill="x")
        
    def reset_fields(self):
        """Reset all form fields"""
        self.ocp_versions_var.set("")
        self.ocp_channel_var.set("stable-4.14")
        self.operators_var.set("")
        self.operator_catalog_var.set("registry.redhat.io/redhat/redhat-operator-index")
        self.additional_images_var.set("")
        self.output_file_var.set("imageset-config.yaml")
        self.helm_charts = []
        self.refresh_helm_tree()
        self.preview_text.delete(1.0, tk.END)
        self.status_var.set("All fields reset")
    
    def add_operator(self, operator_name):
        """Add an operator to the operators field"""
        current = self.operators_var.get()
        if current:
            if operator_name not in current.split(","):
                self.operators_var.set(f"{current},{operator_name}")
        else:
            self.operators_var.set(operator_name)
    
    def browse_output_file(self):
        """Browse for output file location"""
        filename = filedialog.asksaveasfilename(
            title="Save ImageSetConfiguration as",
            defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
        )
        if filename:
            self.output_file_var.set(filename)
    
    def add_helm_chart(self):
        """Add a Helm chart via dialog"""
        dialog = HelmChartDialog(self.root)
        if dialog.result:
            self.helm_charts.append(dialog.result)
            self.refresh_helm_tree()
    
    def remove_helm_chart(self):
        """Remove selected Helm chart"""
        selection = self.helm_tree.selection()
        if selection:
            index = self.helm_tree.index(selection[0])
            del self.helm_charts[index]
            self.refresh_helm_tree()
    
    def refresh_helm_tree(self):
        """Refresh the Helm charts tree view"""
        for item in self.helm_tree.get_children():
            self.helm_tree.delete(item)
        
        for chart in self.helm_charts:
            self.helm_tree.insert("", "end", values=(
                chart["name"],
                chart["repository"],
                chart.get("version", "")
            ))
    
    def generate_preview(self):
        """Generate and display preview of the configuration"""
        try:
            generator = self.create_generator()
            yaml_content = generator.generate_yaml()
            
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(1.0, yaml_content)
            
            self.status_var.set("Preview generated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate preview: {str(e)}")
            self.status_var.set(f"Error: {str(e)}")
    
    def generate_and_save(self):
        """Generate configuration and save to file"""
        try:
            generator = self.create_generator()
            output_file = self.output_file_var.get()
            
            if not output_file:
                messagebox.showerror("Error", "Please specify an output file")
                return
            
            generator.save_to_file(output_file)
            
            # Also update preview
            yaml_content = generator.generate_yaml()
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(1.0, yaml_content)
            
            messagebox.showinfo("Success", f"ImageSetConfiguration saved to {output_file}")
            self.status_var.set(f"Configuration saved to {output_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate and save: {str(e)}")
            self.status_var.set(f"Error: {str(e)}")
    
    def create_generator(self):
        """Create ImageSetGenerator instance with current form data"""
        generator = ImageSetGenerator()
        
        # Add OCP versions
        ocp_versions = self.ocp_versions_var.get().strip()
        if ocp_versions:
            versions = [v.strip() for v in ocp_versions.split(",") if v.strip()]
            channel = self.ocp_channel_var.get()
            generator.add_ocp_versions(versions, channel)
        
        # Add operators with version selection support
        operators = self.operators_var.get().strip()
        if operators:
            operator_list = []
            for op in operators.split(","):
                op = op.strip()
                if op:
                    # If operator has selected versions, create a dict with the info
                    if hasattr(self, 'operator_versions') and op in self.operator_versions:
                        operator_list.append({
                            "name": op,
                            "selectedVersions": self.operator_versions[op]
                        })
                    else:
                        operator_list.append(op)
            
            catalog = self.operator_catalog_var.get()
            generator.add_operators(operator_list, catalog)
        
        # Add additional images
        additional_images = self.additional_images_var.get().strip()
        if additional_images:
            images = [img.strip() for img in additional_images.split(",") if img.strip()]
            generator.add_additional_images(images)
        
        # Add Helm charts
        if self.helm_charts:
            generator.add_helm_charts(self.helm_charts)
        
        return generator
    
    def clear_preview(self):
        """Clear the preview area"""
        self.preview_text.delete(1.0, tk.END)
        self.status_var.set("Preview cleared")
    
    def generate_config(self):
        """Generate and save the ImageSetConfiguration"""
        try:
            # Get values from form
            ocp_versions = [v.strip() for v in self.ocp_versions_var.get().split(",") if v.strip()]
            operators = [op.strip() for op in self.operators_var.get().split(",") if op.strip()]
            additional_images = [img.strip() for img in self.additional_images_var.get().split(",") if img.strip()]
            
            if not ocp_versions and not operators:
                messagebox.showerror("Error", "At least OCP versions or operators must be specified")
                return
            
            # Create generator and build config
            generator = ImageSetGenerator()
            
            if ocp_versions:
                generator.add_ocp_versions(ocp_versions, self.ocp_channel_var.get())
            
            if operators:
                generator.add_operators(operators, self.operator_catalog_var.get())
            
            if additional_images:
                generator.add_additional_images(additional_images)
            
            if self.helm_charts:
                generator.add_helm_charts(self.helm_charts)
            
            # Save to file
            filename = self.output_file_var.get() or "imageset-config.yaml"
            generator.save_to_file(filename)
            
            # Update preview
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(1.0, generator.generate_yaml())
            
            messagebox.showinfo("Success", f"Configuration generated and saved to {filename}")
            self.status_var.set(f"Configuration saved to {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate configuration: {str(e)}")
            self.status_var.set(f"Error: {str(e)}")


class HelmChartDialog:
    """Dialog for adding Helm charts"""
    
    def __init__(self, parent):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Helm Chart")
        self.dialog.geometry("400x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        self.setup_dialog()
        
    def setup_dialog(self):
        """Setup the dialog interface"""
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Chart name
        ttk.Label(main_frame, text="Chart Name:").grid(row=0, column=0, sticky="w", pady=2)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)
        
        # Repository
        ttk.Label(main_frame, text="Repository:").grid(row=1, column=0, sticky="w", pady=2)
        self.repo_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.repo_var, width=40).grid(row=1, column=1, columnspan=2, sticky="ew", pady=2)
        
        # Version
        ttk.Label(main_frame, text="Version (optional):").grid(row=2, column=0, sticky="w", pady=2)
        self.version_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.version_var, width=40).grid(row=2, column=1, columnspan=2, sticky="ew", pady=2)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="Add", command=self.add_chart).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side="left", padx=5)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        
        # Focus on name field
        self.name_var.set("")
        self.dialog.bind('<Return>', lambda e: self.add_chart())
        self.dialog.bind('<Escape>', lambda e: self.cancel())
    
    def add_chart(self):
        """Add the chart and close dialog"""
        name = self.name_var.get().strip()
        repo = self.repo_var.get().strip()
        
        if not name or not repo:
            messagebox.showerror("Error", "Chart name and repository are required")
            return
        
        self.result = {
            "name": name,
            "repository": repo,
            "version": self.version_var.get().strip()
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel and close dialog"""
        self.dialog.destroy()


def main():
    """Main function to run the GUI"""
    root = tk.Tk()
    app = ImageSetGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
