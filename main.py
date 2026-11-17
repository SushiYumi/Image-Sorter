"""Start with: python main.py"""
import tkinter as tk
from tkinter import messagebox


def main():
    root = tk.Tk()
    try:
        from app import ImageSorter
    except ModuleNotFoundError as exc:
        messagebox.showerror('缺少套件', f'{exc}\n\n請執行：python -m pip install -r requirements.txt', parent=root)
        root.destroy()
        return
    ImageSorter(root)
    root.mainloop()


if __name__ == '__main__':
    main()
