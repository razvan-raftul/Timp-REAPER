# -*- coding: utf-8 -*-
# Actualizarea automată a addonului: la pornirea NVDA (după 20 de secunde) citește version.txt din release-ul
# „latest” de pe GitHub. Dacă e o versiune nouă, o descarcă și o instalează. NVDA spune doar procentul,
# din 10 în 10, cu bipurile obișnuite de progres, apoi te întreabă dacă repornești NVDA acum (addonul nou
# intră în lucru după repornire).
# Fără internet sau fără release, tace.

import os
import tempfile
import threading
import urllib.request

import addonHandler
import queueHandler
import tones
import ui
import wx
from logHandler import log

DEPOZIT = "razvan-raftul/Timp-REAPER"


def _addon():
	return addonHandler.getCodeAddon()


def _baza():
	return "https://github.com/%s/releases/download/latest/" % DEPOZIT


def _tuplu(v):
	try:
		return tuple(int(x) for x in str(v).strip().split("."))
	except Exception:
		return (0,)


def _in_nvda(f, *a):
	queueHandler.queueFunction(queueHandler.eventQueue, f, *a)


def _bip(p):
	tones.beep(110 * 2 ** (p / 25.0), 40)     # bipul de progres al NVDA


def _cere(url, timeout=15):
	return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "addon-nvda"}), timeout=timeout)


def verifica_mai_tarziu():
	try:
		info = (_addon().name, _addon().version)
	except Exception:
		return
	wx.CallLater(20000, lambda: threading.Thread(target=_verifica, args=info, daemon=True).start())


def _verifica(nume, instalata):
	try:
		with _cere(_baza() + "version.txt") as r:
			noua = r.read().decode("ascii", "ignore").strip()
	except Exception:
		return
	if not noua or _tuplu(noua) <= _tuplu(instalata):
		return
	cale = os.path.join(tempfile.gettempdir(), nume + ".nvda-addon")
	try:
		with _cere(_baza() + nume + ".nvda-addon", timeout=60) as r, open(cale, "wb") as f:
			total = int(r.headers.get("Content-Length") or 0)
			citit, bip, spus = 0, 0, 0
			while True:
				b = r.read(16384)
				if not b:
					break
				f.write(b)
				citit += len(b)
				if total:
					p = int(citit * 90 / total)          # descărcarea 0–90, instalarea restul
					if p > bip:
						bip = p
						_in_nvda(_bip, p)
					if p // 10 * 10 > spus:
						spus = p // 10 * 10
						_in_nvda(ui.message, "%d la sută" % spus)
	except Exception as e:
		log.error("actualizare %s: descărcarea nu a mers: %s" % (nume, e))
		return
	wx.CallAfter(_instaleaza, cale)


def _instaleaza(cale):
	try:
		from addonStore.install import installAddon
		installAddon(cale)
	except Exception as e:
		log.error("actualizare: instalarea nu a mers: %s" % e)
		return
	_bip(100)
	ui.message("100 la sută")
	wx.CallLater(1500, _intreaba)


def _intreaba():
	import core
	import gui
	try:
		nume = _addon().manifest["summary"]
	except Exception:
		nume = "Un addon"
	raspuns = gui.messageBox(
		"%s are o actualizare nouă. Dorești să repornești NVDA pentru a se actualiza?" % nume,
		"Actualizare", wx.YES_NO | wx.ICON_QUESTION)
	if raspuns == wx.YES:
		core.restart()
