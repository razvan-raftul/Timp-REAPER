# Timp REAPER – addon NVDA
# Cât e pornit (Control Shift Alt T în REAPER), îți spune timpul piesei când derulezi: „3 minute și 30 de secunde”.
# Control Shift Alt I spune oricând unde ești și cât durează piesa. Locul îl află scriptul „Timp REAPER.lua”,
# pe care addonul îl pune singur în REAPER și îl face să pornească odată cu REAPER.

import os
import re
import threading
import time

import api
import globalPluginHandler
import queueHandler
import ui
import wx
from logHandler import log
from scriptHandler import script

from . import actualizare

SCRIPT_LUA = os.path.join(os.path.dirname(__file__), "Timp REAPER.lua")
FISIER = os.path.join(os.environ.get("TEMP", ""), "reaper_timp.txt")
COMANDA = os.path.join(os.environ.get("TEMP", ""), "reaper_timp_comanda.txt")
CATEGORIE = "Timp REAPER"


def citeste():
	try:
		with open(FISIER, encoding="utf-8", errors="replace") as f:
			date = f.read()
	except OSError:
		return None, None
	ident, _, mesaj = date.partition("\n")
	return ident.strip(), mesaj.strip()


def pune_scriptul_in_reaper():
	"""Pune scriptul din addon în folderul Scripts al REAPER (mereu în același loc) și face ca __startup.lua să-l
	pornească de acolo. O cale veche din __startup.lua (de exemplu un folder mutat sau șters) e înlocuită."""
	try:
		with open(SCRIPT_LUA, "rb") as f:
			nou = f.read()
	except OSError:
		return
	resurse = os.path.join(os.environ.get("APPDATA", ""), "REAPER")
	if not os.path.isdir(resurse):
		return                                     # REAPER nu e instalat (sau e portabil)
	scripturi = os.path.join(resurse, "Scripts")
	cale = os.path.join(scripturi, "Timp REAPER.lua")
	try:
		os.makedirs(scripturi, exist_ok=True)
		vechi = None
		if os.path.exists(cale):
			with open(cale, "rb") as f:
				vechi = f.read()
		if vechi != nou:
			with open(cale, "wb") as f:
				f.write(nou)
	except OSError as e:
		log.error("Timp REAPER: nu am putut scrie %s: %s" % (cale, e))
		return
	startup = os.path.join(scripturi, "__startup.lua")
	try:
		with open(startup, encoding="utf-8", errors="replace") as f:
			continut = f.read()
	except OSError:
		continut = ""
	tipar = r"\[\[[^\]]*Timp REAPER[^\]]*\.lua\]\]"
	if re.search(tipar, continut):
		schimbat = re.sub(tipar, lambda m: "[[" + cale + "]]", continut)
	else:
		schimbat = continut + ("\n-- Timp REAPER: spune timpul piesei la derulare\n"
			"do local id = reaper.AddRemoveReaScript(true, 0, [[" + cale + "]], true)\n"
			"if id and id ~= 0 then reaper.Main_OnCommand(id, 0) end end\n")
	if schimbat != continut:
		try:
			with open(startup, "w", encoding="utf-8") as f:
				f.write(schimbat)
		except OSError as e:
			log.error("Timp REAPER: __startup.lua: %s" % e)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = CATEGORIE

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._opreste = threading.Event()
		self._ultimul = citeste()[0]   # nu spunem ce era deja în fișier la pornirea NVDA
		threading.Thread(target=self._bucla, daemon=True).start()
		threading.Thread(target=pune_scriptul_in_reaper, daemon=True).start()
		actualizare.verifica_mai_tarziu()

	def _bucla(self):
		while not self._opreste.wait(0.05):
			ident, mesaj = citeste()
			if ident and ident != self._ultimul:
				self._ultimul = ident
				if mesaj:
					queueHandler.queueFunction(queueHandler.eventQueue, self._spune, mesaj)

	def _spune(self, mesaj):
		ui.message(mesaj)              # fără să oprească vorbirea: se spune după ce termină OSARA

	def _comanda(self, gesture, ce):
		try:
			app = api.getForegroundObject().appModule.appName.lower()
		except Exception:
			app = ""
		if app != "reaper":
			gesture.send()          # în alte programe tasta rămâne a lor
			return
		inainte = self._ultimul
		try:
			with open(COMANDA, "w", encoding="utf-8") as f:
				f.write("%.3f %s" % (time.time(), ce))
		except OSError as e:
			log.error("Timp REAPER: comanda: %s" % e)
			return

		def verifica():
			if self._ultimul == inainte:
				ui.message("Timp REAPER nu rulează. Repornește REAPER.")
		wx.CallLater(1500, verifica)

	@script(description="Pornește sau oprește timpul spus la derulare în REAPER", gesture="kb:control+shift+alt+t")
	def script_comuta(self, gesture):
		self._comanda(gesture, "comuta")

	@script(description="Spune unde ești în piesă și cât durează, în REAPER", gesture="kb:control+shift+alt+i")
	def script_info(self, gesture):
		self._comanda(gesture, "info")

	def terminate(self):
		self._opreste.set()
		super().terminate()
