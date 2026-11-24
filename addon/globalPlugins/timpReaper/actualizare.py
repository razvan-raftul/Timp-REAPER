# -*- coding: utf-8 -*-
# Actualizarea automată a addonului: la pornirea NVDA (după 20 de secunde) citește version.txt din release-ul
# „latest” de pe GitHub. Dacă e o versiune nouă, o descarcă și o instalează.
# Toate addonurile lui Răzvan care au acest fișier lucrează împreună (prin „registrul” comun de mai jos):
# NVDA spune un singur procent pentru toate descărcările, din 10 în 10, cu bipurile de progres, iar la sfârșit
# apare O SINGURĂ fereastră: „Distors REAPER și Timp REAPER au actualizări noi. Dorești să repornești NVDA
# pentru a se actualiza?”. Fără internet sau fără release, tace.

import os
import sys
import tempfile
import threading
import types
import urllib.request

import addonHandler
import queueHandler
import tones
import ui
import wx
from logHandler import log

DEPOZIT = "razvan-raftul/Timp-REAPER"
_CHEIE = "_razvanActualizari"     # același nume în toate addonurile: așa își găsesc registrul comun


def _registru():
	"""Registrul comun tuturor addonurilor din acest NVDA (un singur obiect în sys.modules)."""
	r = sys.modules.get(_CHEIE)
	if r is None:
		r = types.ModuleType(_CHEIE)
		r.lacat = threading.Lock()
		r.in_curs = 0          # câte addonuri încă verifică, descarcă sau instalează
		r.noi = []             # numele addonurilor instalate, care așteaptă repornirea
		r.progres = {}         # addon -> (citit, total)
		r.spus = 0             # ultimul procent spus
		r.bip = 0
		sys.modules[_CHEIE] = r
	return r


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
		a = _addon()
		info = (a.name, a.version, a.manifest["summary"])
	except Exception:
		return
	r = _registru()
	with r.lacat:
		r.in_curs += 1         # numărat de acum, ca fereastra să aștepte și addonul acesta
	wx.CallLater(20000, lambda: threading.Thread(target=_verifica, args=info, daemon=True).start())


def _gata(nume_afisat=None):
	"""Un addon a terminat (cu sau fără actualizare). Când au terminat toate, apare fereastra, o singură dată."""
	r = _registru()
	with r.lacat:
		if nume_afisat:
			r.noi.append(nume_afisat)
		r.in_curs -= 1
		ultimul = r.in_curs <= 0
		noi = list(r.noi) if ultimul else []
		if ultimul:
			r.noi = []
			r.progres = {}
			r.spus = r.bip = 0
	if noi:
		wx.CallAfter(_intreaba, noi)


def _arata_progres(nume, citit, total):
	r = _registru()
	with r.lacat:
		r.progres[nume] = (citit, total)
		c = sum(x[0] for x in r.progres.values())
		t = sum(x[1] for x in r.progres.values())
		p = int(c * 90 / t) if t else 0          # descărcarea 0–90, instalarea restul
		bip = p > r.bip
		if bip:
			r.bip = p
		zece = p // 10 * 10
		spune = zece > r.spus
		if spune:
			r.spus = zece
	if bip:
		_in_nvda(_bip, p)
	if spune:
		_in_nvda(ui.message, "%d la sută" % zece)


def _verifica(nume, instalata, afisat):
	try:
		with _cere(_baza() + "version.txt") as r:
			noua = r.read().decode("ascii", "ignore").strip()
	except Exception:
		_gata()
		return
	if not noua or _tuplu(noua) <= _tuplu(instalata):
		_gata()
		return
	cale = os.path.join(tempfile.gettempdir(), nume + ".nvda-addon")
	try:
		with _cere(_baza() + nume + ".nvda-addon", timeout=60) as r, open(cale, "wb") as f:
			total = int(r.headers.get("Content-Length") or 0)
			citit = 0
			while True:
				b = r.read(16384)
				if not b:
					break
				f.write(b)
				citit += len(b)
				if total:
					_arata_progres(nume, citit, total)
	except Exception as e:
		log.error("actualizare %s: descărcarea nu a mers: %s" % (nume, e))
		_gata()
		return
	wx.CallAfter(_instaleaza, cale, afisat)


def _instaleaza(cale, afisat):
	try:
		from addonStore.install import installAddon
		installAddon(cale)
	except Exception as e:
		log.error("actualizare: instalarea nu a mers: %s" % e)
		_gata()
		return
	_gata(afisat)


def _intreaba(noi):
	import core
	import gui
	_bip(100)
	ui.message("100 la sută")
	if len(noi) == 1:
		text = "%s are o actualizare nouă." % noi[0]
	else:
		text = "%s și %s au actualizări noi." % (", ".join(noi[:-1]), noi[-1])
	text += " Dorești să repornești NVDA pentru a se actualiza?"

	def arata():
		if gui.messageBox(text, "Actualizare", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
			core.restart()
	wx.CallLater(1500, arata)
