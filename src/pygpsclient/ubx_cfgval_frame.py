"""
ubx_cfgval_frame.py

UBX Configuration frame for CFG-VAL commands.

Created on 22 Dec 2020

:author: semuadmin (Steve Smith)
:copyright: 2020 semuadmin
:license: BSD 3-Clause
"""

# pylint: disable=no-member

import csv
from tkinter import (
    EW,
    HORIZONTAL,
    LEFT,
    NORMAL,
    VERTICAL,
    Button,
    E,
    Entry,
    Frame,
    IntVar,
    Label,
    Listbox,
    N,
    Radiobutton,
    S,
    Scrollbar,
    Spinbox,
    StringVar,
    TclError,
    W,
)
from tkinter.filedialog import askopenfilename

from PIL import Image, ImageTk
from pyubx2 import UBX_CONFIG_DATABASE, UBXMessage
from pyubx2.ubxhelpers import attsiz, atttyp, cfgname2key

from pygpsclient.globals import (
    CLICK_CURSOR,
    ERRCOL,
    ICON_BLANK,
    ICON_CONFIRMED,
    ICON_PENDING,
    ICON_SEND,
    ICON_WARNING,
    OKCOL,
    READONLY,
    TRACEMODE_WRITE,
    UBX_CFGVAL,
    VALBOOL,
    VALCUSTOM,
    VALFLOAT,
    VALINT,
    VALNONBLANK,
)
from pygpsclient.helpers import valid_hex

VALSET = 0
VALDEL = 1
VALGET = 2
# u-blox CFG-VAL* messages allow a maximum of 64 keys per message,
# so large batches are split into chunks of this size
MAXKEYS = 64
ATTDICT = {
    "U": "unsigned int",
    "I": "signed int",
    "R": "float",
    "L": "bool",
    "E": "unsigned int",
    "X": "byte(s) as hex string",
    "C": "char(s)",
}


class UBX_CFGVAL_Frame(Frame):
    """
    UBX CFG-VAL configuration command panel.
    """

    def __init__(self, app: Frame, parent: Frame, *args, **kwargs):
        """
        Constructor.

        :param Frame app: reference to main tkinter application
        :param Frame parent: reference to parent frame (config-dialog)
        :param args: optional args to pass to Frame parent class
        :param kwargs: optional kwargs to pass to Frame parent class
        """

        self.__app = app  # Reference to main application class
        self.__master = self.__app.appmaster  # Reference to root class (Tk)
        self.__container = parent

        super().__init__(parent.container, *args, **kwargs)

        self._img_send = ImageTk.PhotoImage(Image.open(ICON_SEND))
        self._img_pending = ImageTk.PhotoImage(Image.open(ICON_PENDING))
        self._img_confirmed = ImageTk.PhotoImage(Image.open(ICON_CONFIRMED))
        self._img_warn = ImageTk.PhotoImage(Image.open(ICON_WARNING))
        self._img_blank = ImageTk.PhotoImage(Image.open(ICON_BLANK))
        self._cfgval_cat = None
        self._cfgval_keyname = None
        self._cfgval_keyid = None
        self._cfgvals = []  # batch queue of parameters to flash together
        self._cfgmode = IntVar()
        self._cfgatt = StringVar()
        self._cfgkeyid = StringVar()
        self._cfgval = StringVar()
        self._cfglayer = StringVar()

        self._body()
        self._do_layout()
        self._attach_events()
        self.reset()

    def _body(self):
        """
        Set up frame and widgets.
        """

        self._lbl_configdb = Label(
            self, text="CFG-VALSET/DEL/GET Configuration Interface", anchor=W
        )
        self._lbl_cat = Label(self, text="Category", anchor=W)
        self._lbx_cat = Listbox(
            self,
            border=2,
            relief="sunken",
            height=10,
            justify=LEFT,
            exportselection=False,
        )
        self._scr_catv = Scrollbar(self, orient=VERTICAL)
        self._scr_cath = Scrollbar(self, orient=HORIZONTAL)
        self._lbx_cat.config(yscrollcommand=self._scr_catv.set)
        self._lbx_cat.config(xscrollcommand=self._scr_cath.set)
        self._scr_catv.config(command=self._lbx_cat.yview)
        self._scr_cath.config(command=self._lbx_cat.xview)
        self._lbl_parm = Label(self, text="Keyname", anchor=W)
        self._lbx_parm = Listbox(
            self,
            border=2,
            relief="sunken",
            height=10,
            justify=LEFT,
            exportselection=False,
        )
        self._scr_parmv = Scrollbar(self, orient=VERTICAL)
        self._scr_parmh = Scrollbar(self, orient=HORIZONTAL)
        self._lbx_parm.config(yscrollcommand=self._scr_parmv.set)
        self._lbx_parm.config(xscrollcommand=self._scr_parmh.set)
        self._scr_parmv.config(command=self._lbx_parm.yview)
        self._scr_parmh.config(command=self._lbx_parm.xview)

        self._rad_cfgset = Radiobutton(
            self, text="CFG-VALSET", variable=self._cfgmode, value=0
        )
        self._rad_cfgdel = Radiobutton(
            self, text="CFG-VALDEL", variable=self._cfgmode, value=1
        )
        self._rad_cfgget = Radiobutton(
            self, text="CFG-VALGET", variable=self._cfgmode, value=2
        )
        self._lbl_key = Label(self, text="KeyID")
        self._lbl_keyid = Label(
            self,
            textvariable=self._cfgkeyid,
            width=10,
            border=1,
            relief="sunken",
        )
        self._lbl_type = Label(self, text="Type")
        self._lbl_att = Label(
            self,
            textvariable=self._cfgatt,
            width=5,
            border=1,
            relief="sunken",
        )
        self._lbl_layer = Label(self, text="Layer")
        self._spn_layer = Spinbox(
            self,
            textvariable=self._cfglayer,
            values=("RAM", "BBR", "FLASH", "DEFAULT"),
            wrap=True,
            width=8,
            state=READONLY,
        )
        self._lbl_val = Label(self, text="Value")
        self._ent_val = Entry(
            self,
            textvariable=self._cfgval,
            state=READONLY,
            relief="sunken",
        )
        self._btn_add = Button(
            self,
            text="Add",
            width=5,
            command=self._on_add,
            cursor=CLICK_CURSOR,
        )

        self._lbl_queue = Label(
            self, text="Batch queue (sent as a single transaction)", anchor=W
        )
        self._lbx_queue = Listbox(
            self,
            border=2,
            relief="sunken",
            height=6,
            justify=LEFT,
            exportselection=False,
        )
        self._scr_queuev = Scrollbar(self, orient=VERTICAL)
        self._scr_queueh = Scrollbar(self, orient=HORIZONTAL)
        self._lbx_queue.config(yscrollcommand=self._scr_queuev.set)
        self._lbx_queue.config(xscrollcommand=self._scr_queueh.set)
        self._scr_queuev.config(command=self._lbx_queue.yview)
        self._scr_queueh.config(command=self._lbx_queue.xview)
        self._btn_remove = Button(
            self,
            text="Remove",
            width=6,
            command=self._on_remove,
            cursor=CLICK_CURSOR,
        )
        self._btn_clear = Button(
            self,
            text="Clear",
            width=6,
            command=self._on_clear,
            cursor=CLICK_CURSOR,
        )
        self._btn_load = Button(
            self,
            text="Load CSV",
            width=6,
            command=self._on_load_csv,
            cursor=CLICK_CURSOR,
        )

        self._lbl_send_command = Label(self)
        self._btn_send_command = Button(
            self,
            image=self._img_send,
            width=50,
            command=self._on_send_config,
            cursor=CLICK_CURSOR,
        )

    def _do_layout(self):
        """
        Layout widgets.
        """

        self._lbl_configdb.grid(column=0, row=0, columnspan=5, sticky=EW)
        self._lbl_cat.grid(column=0, row=1, sticky=EW)
        self._lbx_cat.grid(column=0, row=2, rowspan=10, sticky=EW)
        self._scr_catv.grid(column=0, row=2, rowspan=10, sticky=(N, S, E))
        self._scr_cath.grid(column=0, row=12, sticky=EW)
        self._lbl_parm.grid(column=1, row=1, columnspan=4, sticky=EW)
        self._lbx_parm.grid(column=1, row=2, columnspan=4, rowspan=10, sticky=EW)
        self._scr_parmv.grid(column=4, row=2, rowspan=10, sticky=(N, S, E))
        self._scr_parmh.grid(column=1, row=12, columnspan=4, sticky=EW)
        self._rad_cfgget.grid(column=0, row=13, sticky=W)
        self._rad_cfgset.grid(column=0, row=14, sticky=W)
        self._rad_cfgdel.grid(column=0, row=15, sticky=W)
        self._lbl_key.grid(column=1, row=13, sticky=E)
        self._lbl_keyid.grid(column=2, row=13, sticky=W)
        self._lbl_type.grid(column=3, row=13, sticky=E)
        self._lbl_att.grid(column=4, row=13, sticky=W)
        self._lbl_layer.grid(column=1, row=14, sticky=E)
        self._spn_layer.grid(column=2, row=14, sticky=W)
        self._lbl_val.grid(column=1, row=15, sticky=E)
        self._ent_val.grid(column=2, row=15, columnspan=2, sticky=EW)
        self._btn_add.grid(column=4, row=15, sticky=EW)

        self._lbl_queue.grid(column=0, row=16, columnspan=5, sticky=EW)
        self._lbx_queue.grid(column=0, row=17, columnspan=3, rowspan=4, sticky=EW)
        self._scr_queuev.grid(column=2, row=17, rowspan=4, sticky=(N, S, E))
        self._scr_queueh.grid(column=0, row=21, columnspan=3, sticky=EW)
        self._btn_remove.grid(column=3, row=17, columnspan=2, sticky=EW)
        self._btn_clear.grid(column=3, row=18, columnspan=2, sticky=EW)
        self._btn_load.grid(column=3, row=19, columnspan=2, sticky=EW)

        self._btn_send_command.grid(
            column=3, row=22, rowspan=2, ipadx=3, ipady=3, sticky=E
        )
        self._lbl_send_command.grid(
            column=4, row=22, rowspan=2, ipadx=3, ipady=3, sticky=E
        )
        self.option_add("*Font", self.__app.font_sm)

    def _attach_events(self):
        """
        Bind events to widgets.
        """

        self._lbx_cat.bind("<<ListboxSelect>>", self._on_select_cat)
        self._lbx_parm.bind("<<ListboxSelect>>", self._on_select_parm)
        self._cfgmode.trace_add(TRACEMODE_WRITE, self._on_select_mode)

    def reset(self):
        """
        Reset panel with sorted list of unique UBX Config Database key categories.
        """

        cdb_cats = []
        for cdb in UBX_CONFIG_DATABASE:
            cdbs = cdb.split("_", maxsplit=3)
            cdbp = f"{cdbs[0]}_{cdbs[1]}"
            if cdbs[1] == "MSGOUT":  # subdivide large MSGOUT category
                cdbp += f"_{cdbs[2]}"
            if cdbp not in cdb_cats:
                cdb_cats.append(cdbp)

        for i, cat in enumerate(cdb_cats):
            self._lbx_cat.insert(i, cat)
        self._cfgmode.set(2)
        self._on_clear()
        self._lbl_send_command.config(image=self._img_blank)

    def _on_select_mode(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Mode has been selected.
        """

        if self._cfgmode.get() == VALSET:
            self._ent_val.config(state=NORMAL)
        else:
            self._ent_val.config(state=READONLY)
        # queued items are mode-specific (SET stores values, DEL/GET store
        # keys only), so clear the batch when the mode changes
        self._on_clear()
        self._lbl_send_command.config(image=self._img_blank)

    def _on_select_cat(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Configuration category has been selected.
        """

        idx = self._lbx_cat.curselection()
        self._cfgval_cat = self._lbx_cat.get(idx)

        self._lbx_parm.delete(0, "end")
        self._cfgkeyid.set("")
        self._cfgatt.set("")
        idx = 0
        for keyname, (_, _) in UBX_CONFIG_DATABASE.items():
            if self._cfgval_cat in keyname:
                self._lbx_parm.insert(idx, keyname)
                idx += 1
        self._cfgval.set("")
        self._lbl_send_command.config(image=self._img_blank)

    def _on_select_parm(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Configuration parameter (keyname) has been selected.
        """

        try:
            idx = self._lbx_parm.curselection()
            self._cfgval_keyname = self._lbx_parm.get(idx)

            keyid, att = cfgname2key(self._cfgval_keyname)
            self._cfgkeyid.set(hex(keyid))
            self._cfgatt.set(att)
            self._cfgval.set("")
            self._lbl_send_command.config(image=self._img_blank)
        except TclError:
            pass

    def _parse_current(self):
        """
        Parse and validate the currently selected keyname and value entry.

        Used both to add a parameter to the batch queue and to send a
        single parameter directly. On invalid input the entry is flagged
        and an error status is shown.

        :return: (keyname, value) tuple, or None if invalid
        :rtype: tuple or None
        """

        if self._cfgval_keyname is None:
            return None
        att = atttyp(self._cfgatt.get())
        try:
            atts = attsiz(self._cfgatt.get())
        except ValueError as err:
            self._ent_val.validate(VALNONBLANK)
            self.__container.status_label = (f"INVALID ENTRY - {err}", ERRCOL)
            return None

        val = self._cfgval.get()
        valid = True
        try:
            if att in ("C", "X"):  # byte or char
                valid = self._ent_val.validate(
                    VALCUSTOM,
                    func=valid_hex,
                    args=[
                        atts,
                    ],
                )
                if valid:
                    val = int.to_bytes(int(val, 16), atts, "little")
            elif att in ("E", "U"):  # unsigned integer
                self._ent_val.validate(VALINT)
                val = int(val)
                if val < 0:
                    valid = False
            elif att == "L":  # bool
                self._ent_val.validate(VALBOOL)
                val = int(val)
                if val not in (0, 1):
                    valid = False
            elif att == "I":  # signed integer
                self._ent_val.validate(VALINT)
                val = int(val)
            elif att == "R":  # floating point
                self._ent_val.validate(VALFLOAT)
                val = float(val)
        except ValueError:
            valid = False

        if not valid:
            self._lbl_send_command.config(image=self._img_warn)
            typ = ATTDICT[att]
            self.__container.status_label = (
                (
                    "INVALID ENTRY - must conform to parameter "
                    f"type {att} ({typ}) and size {atts} bytes"
                ),
                ERRCOL,
            )
            return None

        return (self._cfgval_keyname, val)

    def _on_add(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Add the currently selected parameter to the batch queue.

        In CFG-VALSET mode the value is validated and stored; in
        CFG-VALDEL/GET mode only the keyname is required.
        """

        layer = self._cfglayer.get() or "RAM"
        if self._cfgmode.get() == VALSET:
            parsed = self._parse_current()
            if parsed is None:
                return
            keyname, val = parsed
            display = f"{layer:6s} {keyname} = {self._cfgval.get()}"
        else:
            if self._cfgval_keyname is None:
                return
            keyname, val = self._cfgval_keyname, None
            display = f"{layer:6s} {keyname}"

        self._cfgvals.append((layer, keyname, val))
        self._lbx_queue.insert("end", display)
        self._lbl_send_command.config(image=self._img_blank)
        self.__container.status_label = (
            f"{len(self._cfgvals)} parameter(s) queued",
            OKCOL,
        )

    def _on_remove(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Remove the selected parameter(s) from the batch queue.
        """

        for idx in reversed(self._lbx_queue.curselection()):
            self._lbx_queue.delete(idx)
            del self._cfgvals[idx]
        self._lbl_send_command.config(image=self._img_blank)

    def _on_clear(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Clear the batch queue.
        """

        self._cfgvals = []
        self._lbx_queue.delete(0, "end")

    def _on_load_csv(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Load a batch of parameters from a CSV file into the queue.

        The CSV must have columns ``layer,key,value`` where layer is one
        of RAM/BBR/FLASH, key is a pyubx2 config keyname (underscore
        convention) and value is a decimal or hex (0x..) integer. Loading
        switches to CFG-VALSET mode and replaces the current queue.
        """

        fname = askopenfilename(
            title="Load flash parameter CSV",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if not fname:
            return

        self._cfgmode.set(VALSET)  # CSV load targets CFG-VALSET (also clears queue)
        self._on_clear()
        loaded = 0
        unknown = 0
        bad = 0
        try:
            with open(fname, "r", encoding="utf-8", newline="") as fcsv:
                for cells in csv.reader(fcsv):
                    if not cells or cells[0].strip().startswith("#"):
                        continue
                    cells = [c.strip() for c in cells]
                    if cells[0].lower() == "layer":  # header row
                        continue
                    if len(cells) < 3:
                        bad += 1
                        continue
                    layer, key, rawval = cells[0].upper(), cells[1], cells[2]
                    if layer not in ("RAM", "BBR", "FLASH"):
                        bad += 1
                        continue
                    key = key.replace("-", "_")
                    if key not in UBX_CONFIG_DATABASE:
                        unknown += 1
                        continue
                    try:
                        val = self._coerce_value(key, rawval)
                    except (ValueError, KeyError):
                        bad += 1
                        continue
                    self._cfgvals.append((layer, key, val))
                    self._lbx_queue.insert("end", f"{layer:6s} {key} = {rawval}")
                    loaded += 1
        except OSError as err:
            self.__container.status_label = (f"Error reading file - {err}", ERRCOL)
            return

        status = f"Loaded {loaded} parameter(s) from CSV"
        if unknown:
            status += f"; {unknown} unknown key(s) skipped"
        if bad:
            status += f"; {bad} invalid row(s) skipped"
        self.__container.status_label = (status, OKCOL if loaded else ERRCOL)
        self._lbl_send_command.config(image=self._img_blank)

    def _coerce_value(self, keyname: str, rawval: str):
        """
        Coerce a CSV value string into the correct type for its keyname.

        :param str keyname: pyubx2 config keyname
        :param str rawval: value as a decimal or hex string
        :return: value coerced to int, float or bytes per the parameter type
        """

        _, att_full = cfgname2key(keyname)
        att = atttyp(att_full)
        if att == "R":  # floating point
            return float(rawval)
        intval = int(rawval, 16) if rawval.lower().startswith("0x") else int(rawval)
        if att in ("C", "X"):  # char or byte(s)
            return int.to_bytes(intval, attsiz(att_full), "little")
        return intval

    def _on_send_config(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Config interface send button has been clicked.

        Every parameter in the batch queue is sent, grouped by memory
        layer and split into chunks of at most ``MAXKEYS`` keys per
        message. If the queue is empty the currently selected parameter
        is sent on its own (preserving the original behaviour).
        """

        self._lbl_send_command.config(image=self._img_blank)
        mode = self._cfgmode.get()

        if self._cfgvals:
            cfgvals = list(self._cfgvals)
        elif self._cfgval_keyname is not None:
            layer = self._cfglayer.get() or "RAM"
            if mode == VALSET:
                parsed = self._parse_current()
                if parsed is None:
                    return
                keyname, val = parsed
                cfgvals = [(layer, keyname, val)]
            else:
                cfgvals = [(layer, self._cfgval_keyname, None)]
        else:
            return

        if mode == VALSET:
            self._do_valset(cfgvals)
        elif mode == VALDEL:
            self._do_valdel(cfgvals)
        else:
            self._do_valget(cfgvals)

    @staticmethod
    def _group_by_layer(cfgvals: list) -> dict:
        """
        Group queue items by layer, preserving insertion order.

        :param list cfgvals: list of (layer, keyname, value) tuples
        :return: dict of layer -> list of (keyname, value) tuples
        :rtype: dict
        """

        groups = {}
        for layer, keyname, val in cfgvals:
            groups.setdefault(layer, []).append((keyname, val))
        return groups

    @staticmethod
    def _chunk(seq: list, size: int):
        """
        Yield successive ``size``-length chunks of ``seq``.
        """

        for i in range(0, len(seq), size):
            yield seq[i : i + size]

    @staticmethod
    def _layer_setmask(layer: str) -> int:
        """
        Return the CFG-VALSET / CFG-VALDEL layer bitmask for a layer name.

        :param str layer: layer name (RAM, BBR or FLASH)
        :return: layer bitmask (RAM=1, BBR=2, FLASH=4)
        :rtype: int
        """

        return {"BBR": 2, "FLASH": 4}.get(layer, 1)

    @staticmethod
    def _layer_getnum(layer: str) -> int:
        """
        Return the CFG-VALGET layer number for a layer name.

        :param str layer: layer name (RAM, BBR, FLASH or DEFAULT)
        :return: layer number (RAM=0, BBR=1, FLASH=2, DEFAULT=7)
        :rtype: int
        """

        return {"BBR": 1, "FLASH": 2, "DEFAULT": 7}.get(layer, 0)

    def _do_valset(self, cfgvals: list):
        """
        Send CFG-VALSET message(s) setting one or more parameters.

        Parameters are grouped by layer and split into chunks of at most
        MAXKEYS keys per message.

        :param list cfgvals: list of (layer, keyname, value) tuples
        """

        transaction = 0
        nmsg = ntotal = 0
        for layer, items in self._group_by_layer(cfgvals).items():
            mask = self._layer_setmask(layer)
            for chunk in self._chunk(items, MAXKEYS):
                msg = UBXMessage.config_set(mask, transaction, chunk)
                self.__container.send_command(msg)
                nmsg += 1
                ntotal += len(chunk)
        self._lbl_send_command.config(image=self._img_pending)
        self.__container.status_label = (
            f"CFG-VALSET sent - {ntotal} parameter(s) in {nmsg} message(s)"
        )
        for msgid in ("ACK-ACK", "ACK-NAK"):
            self.__container.set_pending(msgid, UBX_CFGVAL)

    def _do_valdel(self, cfgvals: list):
        """
        Send CFG-VALDEL message(s) deleting one or more parameters.

        :param list cfgvals: list of (layer, keyname, value) tuples
        """

        transaction = 0
        nmsg = ntotal = 0
        for layer, items in self._group_by_layer(cfgvals).items():
            mask = self._layer_setmask(layer)
            keys = [key for key, _ in items]
            for chunk in self._chunk(keys, MAXKEYS):
                msg = UBXMessage.config_del(mask, transaction, chunk)
                self.__container.send_command(msg)
                nmsg += 1
                ntotal += len(chunk)
        self._lbl_send_command.config(image=self._img_pending)
        self.__container.status_label = (
            f"CFG-VALDEL sent - {ntotal} parameter(s) in {nmsg} message(s)"
        )
        for msgid in ("ACK-ACK", "ACK-NAK"):
            self.__container.set_pending(msgid, UBX_CFGVAL)

    def _do_valget(self, cfgvals: list):
        """
        Send CFG-VALGET message(s) polling one or more parameters.

        :param list cfgvals: list of (layer, keyname, value) tuples
        """

        transaction = 0
        nmsg = ntotal = 0
        for layer, items in self._group_by_layer(cfgvals).items():
            num = self._layer_getnum(layer)
            keys = [key for key, _ in items]
            for chunk in self._chunk(keys, MAXKEYS):
                msg = UBXMessage.config_poll(num, transaction, chunk)
                self.__container.send_command(msg)
                nmsg += 1
                ntotal += len(chunk)
        self._lbl_send_command.config(image=self._img_pending)
        self.__container.status_label = (
            f"CFG-VALGET sent - {ntotal} parameter(s) in {nmsg} message(s)"
        )
        for msgid in ("CFG-VALGET", "ACK-ACK", "ACK-NAK"):
            self.__container.set_pending(msgid, UBX_CFGVAL)

    def _format_getval(self, keyname: str, val) -> str:
        """
        Format a value returned by CFG-VALGET for display.

        :param str keyname: configuration keyname
        :param val: returned value
        :return: display string
        :rtype: str
        """

        if isinstance(val, bytes):
            _, att = cfgname2key(keyname)
            atts = attsiz(att)
            vali = int.from_bytes(val, "little")
            return f"0x{vali:0{atts*2}x}"
        return val

    def update_status(self, msg: UBXMessage):  # pylint: disable=unused-argument
        """
        Update pending confirmation status.

        :param UBXMessage msg: UBX config message
        """

        if msg.identity == "CFG-VALGET":
            self._lbl_send_command.config(image=self._img_confirmed)
            # populate value entry for the currently selected keyname
            if self._cfgval_keyname is not None:
                val = getattr(msg, self._cfgval_keyname, None)
                if val is not None:
                    self._cfgval.set(self._format_getval(self._cfgval_keyname, val))
            # populate returned values against any queued keynames
            for i, (layer, keyname, _) in enumerate(self._cfgvals):
                val = getattr(msg, keyname, None)
                if val is not None:
                    self._lbx_queue.delete(i)
                    self._lbx_queue.insert(
                        i,
                        f"{layer:6s} {keyname} = {self._format_getval(keyname, val)}",
                    )
            self.__container.status_label = ("CFG-VALGET GET message received", OKCOL)

        elif msg.identity == "ACK-ACK":
            self._lbl_send_command.config(image=self._img_confirmed)
            self.__container.status_label = ("CFG-VAL command acknowledged", OKCOL)

        elif msg.identity == "ACK-NAK":
            self._lbl_send_command.config(image=self._img_warn)
            self.__container.status_label = ("CFG-VAL command rejected", ERRCOL)
