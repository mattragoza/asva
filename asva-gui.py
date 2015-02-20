# ACTIGRAPHY SLEEP VARIABLE ANALYSIS
# Merged from main_sleep_analysis_v5.py and verify_activity.py
# Copyright 2015 Matt Ragoza

import os
import asva
import Tkinter
from tkFileDialog import *
import ttk

def commandOpen():

	return app.askopenfilename(self, parent)

def gui():

	app.mainloop()

class asvaApp(Tkinter.Tk):
	def __init__(self, parent, path):
		Tkinter.Tk.__init__(self, parent)
		self.parent = parent
		self.title("Actigraphy Sleep Variable Analysis | Version " + asva.VERSION)
		self.geometry("800x600")
		self.resizable(False, False)
		self.update()
		self.geometry(self.geometry())

		self.menuBar = Tkinter.Menu(self)
		self.fileMenu = Tkinter.Menu(self.menuBar, tearoff=0)
		self.fileMenu.add_command(label="New")
		self.fileMenu.add_command(label="Open", command=commandOpen)
		self.fileMenu.add_command(label="Save")
		self.fileMenu.add_separator()
		self.fileMenu.add_command(label="Exit", command=self.quit)
		self.menuBar.add_cascade(label="File", menu=self.fileMenu)
		self.config(menu=self.menuBar)

		self.awcList = []
		self.awcListbox = Tkinter.Listbox(self)

		self.fileTree = ttk.Treeview(self, height=27)
		abspath = os.path.abspath(path)
		rootNode = self.fileTree.insert("", "end", text=abspath, open=True)
		self.displayDir(rootNode, abspath)

		self.fileTree.grid(row=0, column=0, padx=6, pady=6)

	def displayDir(self, parent, path):
		for i in os.listdir(path):
			abspath = os.path.join(path, i)
			isdir = os.path.isdir(abspath)
			oid = self.fileTree.insert(parent, "end", text=i, open=False)
			if isdir: self.displayDir(oid, abspath)


if __name__ == "__main__" :
	app = asvaApp(None, os.getcwd())
	gui()
