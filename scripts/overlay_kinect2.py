"""
overlay_kinect2.py
--------------------
Overlay REC / pausa / foto / X / levetta gamma per la Kinect Camera 2.

È lo STESSO overlay della Kinect Camera 1 (overlay_rec.py): stesse icone,
stessi comandi a tocco, stessi pulsanti fisici. Cambia solo dove e come
salva, per tenere separate le registrazioni del Kinect v2:

    video -> ~/Desktop/ki_la_visto/registrazioni/Kinect v2/video/v2_NNNN_DDMMYY.mp4
    foto  -> ~/Desktop/ki_la_visto/registrazioni/Kinect v2/foto/fotov2_NNNN_DDMMYY.jpg

overlay_rec.py NON viene modificato: qui lo estendiamo, così la Camera 1
resta esattamente com'era.

Audio (microfono del Kinect v2, 4 microfoni, 16 kHz, 24 bit utili):
  Il microfono viene ascoltato di continuo da quando la camera si apre
  (arecord, in un thread a parte), ma i dati finiscono nel file SOLO mentre
  si registra e non si è in pausa: così audio e video partono, si fermano e
  vanno in pausa insieme. Allo stop:
    v2_NNNN_DDMMYY.wav  -> i 4 canali GREZZI, intatti (tutto il rumore)
    v2_NNNN_DDMMYY.mp4  -> il video con l'audio: stereo (microfono 1 a
                           sinistra, 4 a destra, i due più distanti),
                           alzato di volume e con un limitatore che evita
                           solo la distorsione sui suoni forti. Nessuna
                           riduzione del rumore.
  L'unione la fa ffmpeg in sottofondo (pochi secondi): la camera non si
  blocca. Senza ffmpeg o senza microfono il video si salva comunque, muto.

Durata dei video:
  Con il Kinect v1 gli fps erano sempre 30, quindi bastava scrivere ogni
  frame in un video a 30 fps. Col v2 sul Pi gli fps reali possono essere
  meno di 30 (dipende dalla GPU), e allora il video uscirebbe accelerato.
  Qui ogni frame viene scritto tante volte quante servono a coprire il tempo
  reale trascorso: il video dura sempre esattamente quanto la registrazione.
"""

import os
import shlex
import shutil
import subprocess
import threading
import time
import wave
from datetime import datetime

import cv2
import numpy as np

from overlay_rec import ControlliOverlay, Registrazione, _prossimo_numero, _percorso_univoco

CARTELLA_BASE_V2 = os.path.expanduser("~/Desktop/ki_la_visto/registrazioni/Kinect v2")
CARTELLA_VIDEO_V2 = os.path.join(CARTELLA_BASE_V2, "video")
CARTELLA_FOTO_V2 = os.path.join(CARTELLA_BASE_V2, "foto")
os.makedirs(CARTELLA_VIDEO_V2, exist_ok=True)
os.makedirs(CARTELLA_FOTO_V2, exist_ok=True)

PREFISSO_VIDEO = "v2"
PREFISSO_FOTO = "fotov2"
FPS_VIDEO_V2 = 30
# Se il Kinect si blocca per un attimo, il video "riempie" il buco ripetendo
# l'ultimo frame, così resta allineato all'audio (che non si ferma mai).
# Oltre questo limite il buco non viene riempito (blocco anomalo).
SALTO_MASSIMO_S = 3.0

# --- Microfono ----------------------------------------------------------
# "Sensor" è il nome della scheda audio del Kinect v2 (arecord -l):
# usarlo al posto del numero evita problemi se il numero cambia.
DISPOSITIVO_AUDIO = "hw:CARD=Sensor,DEV=0"
CANALI_AUDIO = 4
FREQ_AUDIO = 16000
BYTE_CAMPIONE = 4   # S32_LE: 32 bit, di cui 24 di audio vero
BLOCCO_AUDIO_S = 0.02  # pezzetti da 20 ms: audio e video restano allineati entro ~20 ms
COMANDO_MICROFONO = ["arecord", "-q", "-D", DISPOSITIVO_AUDIO, "-c", str(CANALI_AUDIO),
                     "-r", str(FREQ_AUDIO), "-f", "S32_LE", "-t", "raw",
                     "-F", "20000", "-B", "200000"]

# --- Audio nel video finale ------------------------------------------------
CANALE_SINISTRO = 1      # microfoni 1..4; 1 e 4 sono i più distanti fra loro.
CANALE_DESTRO = 4        # Se destra e sinistra risultano invertite, scambia questi due.
GUADAGNO_AUDIO_DB = 24   # il microfono grezzo è molto basso (picchi intorno a -30 dB)


def _log_audio(testo):
    print(f"[AUDIO] {testo}", flush=True)


class MicrofonoKinect:
    """Ascolta di continuo il microfono del Kinect (arecord in un processo,
    letto da un thread). Scrive nel WAV solo quando 'registra' è attivo.

    Si RICONNETTE DA SOLO: quando una camera apre il Kinect, libfreenect2
    fa un reset USB dell'intero dispositivo, e questo stacca anche la parte
    audio (il microfono "muore"). Qui arecord viene semplicemente rilanciato
    finché i dati tornano. Una sorveglianza lo rilancia anche se resta
    appeso senza dare dati, o se dà solo zeri (un microfono vero non è mai
    perfettamente zero). Se il microfono cade durante una registrazione, il
    buco viene riempito di silenzio: l'audio resta allineato al video."""

    def __init__(self):
        self.disponibile = False   # True mentre arrivano dati veri
        self.utilizzabile = shutil.which(COMANDO_MICROFONO[0]) is not None
        self.livello = 0.0          # 0..1, ultimo pezzetto letto
        self._picco = 0.0           # picco dall'ultima volta che qualcuno l'ha chiesto
        self._wav = None
        self._scrivi = False
        self._chiusura = False
        self._lucchetto = threading.Lock()
        self._proc = None
        self._t_avvio_proc = 0.0
        self._t_ultimi_dati = 0.0
        self._t_ultimo_non_zero = 0.0
        self._t_fine_wav = None     # ora dell'ultimo pezzetto scritto nel WAV
        self._ripartito = False     # il prossimo pezzetto arriva dopo una riconnessione
        if not self.utilizzabile:
            _log_audio(f"{COMANDO_MICROFONO[0]} non trovato: video senza audio")
            return
        threading.Thread(target=self._ciclo, daemon=True).start()
        threading.Thread(target=self._sorveglia, daemon=True).start()

    def _ciclo(self):
        """Lancia arecord e lo rilancia ogni volta che si interrompe."""
        primo_giro = True
        self._segnalato = False
        while not self._chiusura:
            try:
                proc = subprocess.Popen(COMANDO_MICROFONO, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
            except Exception as ex:
                if not self._segnalato:
                    _log_audio(f"Microfono non avviato ({ex}): riprovo...")
                    self._segnalato = True
                time.sleep(1.0)
                continue
            ora = time.time()
            self._t_avvio_proc = self._t_ultimo_non_zero = ora
            self._proc = proc
            self._ripartito = not primo_giro
            primo_giro = False
            self._leggi(proc)
            self.disponibile = False
            if self._chiusura:
                break
            try:
                proc.kill()
                errore = proc.stderr.read().decode(errors="replace").strip()
            except Exception:
                errore = ""
            if not self._segnalato:  # un solo messaggio per ogni interruzione
                _log_audio(f"Microfono interrotto ({errore or 'nessun dato'}): mi riconnetto...")
                self._segnalato = True
            time.sleep(0.5)

    def _leggi(self, proc):
        blocco = int(FREQ_AUDIO * BLOCCO_AUDIO_S) * CANALI_AUDIO * BYTE_CAMPIONE
        annunciato = False
        while True:
            dati = proc.stdout.read(blocco)
            if not dati:
                break
            ora = time.time()
            n = len(dati) // (4 * CANALI_AUDIO) * CANALI_AUDIO
            dati = dati[: n * 4]
            campioni = np.frombuffer(dati, "<i4")
            if not campioni.size:
                continue
            self._t_ultimi_dati = ora
            if np.any(campioni):
                self._t_ultimo_non_zero = ora
            self.disponibile = (ora - self._t_ultimo_non_zero) < 2.0
            if self.disponibile and not annunciato:
                _log_audio("Microfono attivo")
                annunciato = True
                self._segnalato = False
            # "somma" dei 4 microfoni (la media), e il suo picco
            somma = campioni.reshape(-1, CANALI_AUDIO).astype(np.float32).mean(axis=1)
            self.livello = float(np.abs(somma).max()) / 2 ** 31
            self._picco = max(self._picco, self.livello)
            with self._lucchetto:
                if self._wav is not None and self._scrivi:
                    durata = n / CANALI_AUDIO / FREQ_AUDIO
                    if self._ripartito and self._t_fine_wav is not None:
                        # microfono ripartito durante la registrazione:
                        # silenzio al posto del pezzo perso, così resta in sincro
                        buco = min(10.0, ora - durata - self._t_fine_wav)
                        if buco > 0.02:
                            frame_buco = int(buco * FREQ_AUDIO)
                            self._wav.writeframes(bytes(frame_buco * CANALI_AUDIO * BYTE_CAMPIONE))
                            _log_audio(f"Riempito un buco di {buco:.2f}s di silenzio")
                    self._wav.writeframes(dati)
                    self._t_fine_wav = ora
                self._ripartito = False

    def _sorveglia(self):
        """Se arecord resta vivo ma non dà dati (o solo zeri), lo chiudiamo:
        il ciclo principale lo rilancerà."""
        while not self._chiusura:
            time.sleep(0.5)
            proc = self._proc
            if proc is None or proc.poll() is not None:
                continue
            ora = time.time()
            senza_dati = ora - max(self._t_ultimi_dati, self._t_avvio_proc)
            solo_zeri = ora - self._t_ultimo_non_zero
            if senza_dati > 2.0 or solo_zeri > 3.0:
                try:
                    proc.kill()
                except Exception:
                    pass

    def prendi_picco(self):
        """Il picco dall'ultima chiamata (così i suoni brevi fra un disegno e
        l'altro non si perdono), poi riparte da zero."""
        p, self._picco = self._picco, 0.0
        return p

    def inizia(self, percorso_wav):
        with self._lucchetto:
            w = wave.open(percorso_wav, "wb")
            w.setnchannels(CANALI_AUDIO)
            w.setsampwidth(BYTE_CAMPIONE)
            w.setframerate(FREQ_AUDIO)
            self._wav = w
            self._scrivi = True
            self._t_fine_wav = None

    def pausa(self, in_pausa):
        with self._lucchetto:
            self._scrivi = not in_pausa
            self._t_fine_wav = None  # il tempo in pausa non va riempito

    def finisci(self):
        with self._lucchetto:
            if self._wav is not None:
                self._wav.close()
                self._wav = None
            self._scrivi = False

    def chiudi(self):
        self._chiusura = True
        self.finisci()
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                # aspettiamo che arecord sia davvero chiuso: il microfono si può
                # aprire da un solo programma alla volta (GUI -> camera)
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()


# --- Indicatore di livello (VU) ------------------------------------------
# Scala dell'indicatore: dB come finiranno NEL VIDEO (cioè già alzati di
# GUADAGNO_AUDIO_DB). 0 = massimo, sotto VU_MIN_DB = silenzio.
VU_MIN_DB = -48.0
VU_GIALLO_DB = -12.0
VU_ROSSO_DB = -3.0


class StrumentoLivello:
    """La "lancetta" di un VU meter: sale subito, scende con calma (così si
    legge), e tiene il picco per un attimo come nei programmi audio."""

    def __init__(self, caduta_db_al_s=30.0, tenuta_picco_s=1.2):
        self.db = VU_MIN_DB
        self.picco_db = VU_MIN_DB
        self._caduta = caduta_db_al_s
        self._tenuta = tenuta_picco_s
        self._t = time.time()
        self._t_picco = 0.0

    def aggiorna(self, livello_lineare):
        ora = time.time()
        dt, self._t = ora - self._t, ora
        db = 20 * np.log10(max(livello_lineare, 1e-9)) + GUADAGNO_AUDIO_DB
        self.db = max(db, self.db - self._caduta * dt, VU_MIN_DB)
        if self.db >= self.picco_db:
            self.picco_db, self._t_picco = self.db, ora
        elif ora - self._t_picco > self._tenuta:
            self.picco_db = max(self.db, self.picco_db - self._caduta * dt)
        return self.db

    @staticmethod
    def frazione(db):
        return float(np.clip((db - VU_MIN_DB) / -VU_MIN_DB, 0, 1))


def _unisci_audio_video(muto, wav, finale):
    """Unisce video muto + WAV in 'finale', in sottofondo (processo staccato:
    finisce anche se la camera viene chiusa subito dopo). Se qualcosa va
    storto, il video muto diventa comunque il file finale e il WAV resta."""
    try:
        with wave.open(wav) as w:
            vuoto = w.getnframes() == 0
    except Exception:
        vuoto = True
    if vuoto:
        os.replace(muto, finale)
        try:
            os.remove(wav)
        except OSError:
            pass
        _log_audio("Nessun audio arrivato dal microfono: video salvato senza audio")
        return
    if not shutil.which("ffmpeg"):
        os.replace(muto, finale)
        _log_audio("ffmpeg non trovato: video salvato senza audio, l'audio è nel .wav "
                   "(per unirli in automatico: sudo apt install ffmpeg)")
        return
    parte = finale[:-4] + "_unione.mp4"
    q = shlex.quote
    sx, dx = CANALE_SINISTRO - 1, CANALE_DESTRO - 1
    filtro = (f"[1:a]pan=stereo|c0=c{sx}|c1=c{dx},volume={GUADAGNO_AUDIO_DB}dB,"
              f"alimiter=limit=0.9,aresample=48000[a]")
    comando = (f"ffmpeg -nostdin -loglevel error -y -i {q(muto)} -i {q(wav)} "
               f"-filter_complex {q(filtro)} -map 0:v -map '[a]' -c:v copy "
               f"-c:a aac -b:a 160k -shortest {q(parte)} "
               f"&& mv -f {q(parte)} {q(finale)} && rm -f {q(muto)} "
               f"|| {{ rm -f {q(parte)}; mv -f {q(muto)} {q(finale)}; }}")
    subprocess.Popen(["sh", "-c", comando], start_new_session=True)
    _log_audio(f"Unione audio+video in corso -> {finale}")


class RegistrazioneV2(Registrazione):
    def __init__(self, larghezza, altezza, microfono=None):
        super().__init__(larghezza, altezza)
        self.numero_clip = _prossimo_numero(CARTELLA_VIDEO_V2, PREFISSO_VIDEO)
        self.microfono = microfono
        self._percorso_finale = None
        self._percorso_wav = None
        self._t_ultimo = None
        self._tempo_registrato = 0.0
        self._frame_scritti = 0

    def nome_prossima_clip(self):
        data = datetime.now().strftime("%d%m%y")
        return f"{PREFISSO_VIDEO}_{self.numero_clip:04d}_{data}"

    def avvia(self):
        if self.attiva:
            return
        base = self.nome_prossima_clip()
        self._percorso_finale = _percorso_univoco(CARTELLA_VIDEO_V2, base, "mp4")
        self._percorso_wav = None
        if self.microfono is not None and self.microfono.utilizzabile:
            # video e audio in due file separati, uniti allo stop
            radice = self._percorso_finale[:-4]
            self.percorso_clip = radice + "_muto.mp4"
            self._percorso_wav = radice + ".wav"
            self.microfono.inizia(self._percorso_wav)
        else:
            self.percorso_clip = self._percorso_finale
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(self.percorso_clip, fourcc, FPS_VIDEO_V2,
                                      (self.larghezza, self.altezza))
        self.attiva = True
        self.in_pausa = False
        self.secondi_registrati = 0.0
        self._t_ultimo = None
        self._tempo_registrato = 0.0
        self._frame_scritti = 0
        print(f"[REC] Avviata: {self._percorso_finale} "
              f"({'con audio' if self._percorso_wav else 'senza audio'})", flush=True)

    def metti_in_pausa(self):
        super().metti_in_pausa()
        if self._percorso_wav:
            self.microfono.pausa(True)

    def riprendi(self):
        super().riprendi()
        if self._percorso_wav:
            self.microfono.pausa(False)

    def ferma(self):
        if not self.attiva:
            return
        muto, wav, finale = self.percorso_clip, self._percorso_wav, self._percorso_finale
        super().ferma()  # chiude il video (e passa al numero di clip successivo)
        if wav:
            self.microfono.finisci()
            _unisci_audio_video(muto, wav, finale)
        self._percorso_wav = None
        self._percorso_finale = None

    def nome_da_mostrare(self):
        if self.attiva and self._percorso_finale:
            return os.path.splitext(os.path.basename(self._percorso_finale))[0]
        return self.nome_prossima_clip()

    def scrivi_se_attiva(self, frame_bgr_pulito):
        if not self.attiva or self.writer is None:
            return
        ora = time.time()
        dt = 0.0 if self._t_ultimo is None else min(ora - self._t_ultimo, SALTO_MASSIMO_S)
        self._t_ultimo = ora  # aggiornato anche in pausa: il tempo in pausa non conta
        if self.in_pausa:
            return
        self._tempo_registrato += dt
        dovuti = int(self._tempo_registrato * FPS_VIDEO_V2) + 1
        while self._frame_scritti < dovuti:
            self.writer.write(frame_bgr_pulito)
            self._frame_scritti += 1
        self.secondi_registrati = self._frame_scritti / FPS_VIDEO_V2


def salva_foto_v2(frame_bgr_pulito):
    data = datetime.now().strftime("%d%m%y")
    numero = _prossimo_numero(CARTELLA_FOTO_V2, PREFISSO_FOTO)
    base = f"{PREFISSO_FOTO}_{numero:04d}_{data}"
    percorso = _percorso_univoco(CARTELLA_FOTO_V2, base, "jpg")
    cv2.imwrite(percorso, frame_bgr_pulito)
    print(f"[FOTO] Salvata: {percorso}", flush=True)


class ControlliOverlayV2(ControlliOverlay):
    """Come ControlliOverlay della Camera 1, ma registra con RegistrazioneV2
    e salva le foto nella cartella del Kinect v2.

    Selettore di modalità (con_modo=True, usato dalla camera K): invece delle
    freccine minuscole del v1, in basso al centro ci sono due pulsanti
    tondi grandi come le altre icone, con in mezzo "MODO N  NOME".
    nomi_modo: dict facoltativo {1: "GRIGIO", 2: "TURBO", ...}."""

    def __init__(self, nomi_modo=None, misura_registrazione=None, con_audio=True, **kwargs):
        super().__init__(**kwargs)
        # misura_registrazione: (larghezza, altezza) dei video e delle foto,
        # se diversa da quella a schermo. Serve alla camera normale: registra
        # in Full HD ma mostra un'anteprima più piccola, così le icone
        # restano grandi. Se non la dai, registra alla misura dello schermo.
        self.misura_registrazione = misura_registrazione or (self.larghezza, self.altezza)
        self.microfono = MicrofonoKinect() if con_audio else None
        self.registrazione = RegistrazioneV2(*self.misura_registrazione, microfono=self.microfono)
        self.nomi_modo = nomi_modo or {}
        self.vu = StrumentoLivello()

        # Levetta della gamma ORIZZONTALE in alto (a sinistra meno, a destra
        # più): l'analogico la muove in orizzontale. Il verticale resta
        # libero per il futuro zoom.
        self.gamma_y = 56
        self.gamma_x0 = 50
        self.gamma_x1 = self.larghezza - 90
        self.trascinamento_gamma = False

        # VU meter verticale a sinistra (dove prima c'era la gamma)
        self.vu_x = 8
        self.vu_larghezza = 12
        self.vu_y0 = 88
        self.vu_y1 = self.altezza - 44
        self.vu_segmenti = max(10, (self.vu_y1 - self.vu_y0) // 12)

        if self.con_modo:
            # Le stesse variabili che usa on_mouse del v1 per il tocco sulle
            # frecce: cambiandole qui, anche il tocco segue i nuovi pulsanti.
            self.raggio_freccia = 17
            self.y_modo = self.altezza - 30
            self.x_modo_centro = self.larghezza // 2
            self.x_freccia_sx = self.x_modo_centro - 105
            self.x_freccia_dx = self.x_modo_centro + 105

    def disegna(self, frame_bgr_pulito):
        # Le parti del v1 che qui rifacciamo diverse (freccine della
        # modalità, gamma verticale) le spegniamo durante il disegno base.
        con_modo, con_gamma = self.con_modo, self.con_gamma
        self.con_modo = self.con_gamma = False
        try:
            frame = super().disegna(frame_bgr_pulito)
        finally:
            self.con_modo, self.con_gamma = con_modo, con_gamma
        if con_modo:
            self._disegna_selettore_modo(frame)
        if con_gamma:
            self._disegna_gamma_orizzontale(frame)
        self._disegna_vu(frame)
        return frame

    # --- gamma orizzontale ------------------------------------------------
    def _x_da_gamma(self):
        f = (self.stato_gamma["gamma"] - self.gamma_min) / (self.gamma_max - self.gamma_min)
        return int(self.gamma_x0 + f * (self.gamma_x1 - self.gamma_x0))

    def _gamma_da_x(self, x):
        x = max(self.gamma_x0, min(self.gamma_x1, x))
        f = (x - self.gamma_x0) / (self.gamma_x1 - self.gamma_x0)
        self.stato_gamma["gamma"] = round(self.gamma_min + f * (self.gamma_max - self.gamma_min), 3)

    def _disegna_gamma_orizzontale(self, frame):
        y = self.gamma_y
        cv2.line(frame, (self.gamma_x0, y), (self.gamma_x1, y), (150, 150, 150), 3, cv2.LINE_AA)
        for x in (self.gamma_x0, self.gamma_x1):  # piccole tacche ai due estremi
            cv2.line(frame, (x, y - 6), (x, y + 6), (150, 150, 150), 2, cv2.LINE_AA)
        x = self._x_da_gamma()
        cv2.circle(frame, (x, y), self.raggio_maniglia, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, (x, y), self.raggio_maniglia, (30, 30, 30), 2, cv2.LINE_AA)
        cv2.putText(frame, "GAMMA", (self.gamma_x1 + 12, y + 4), cv2.FONT_HERSHEY_SIMPLEX,
                    0.35, (210, 210, 210), 1, cv2.LINE_AA)

    def on_mouse(self, event, x, y, flags, userdata):
        if self.con_gamma:
            sulla_levetta = (abs(y - self.gamma_y) <= 18 and
                             self.gamma_x0 - 15 <= x <= self.gamma_x1 + 15)
            if event == cv2.EVENT_LBUTTONDOWN and sulla_levetta:
                self.trascinamento_gamma = True
                self._gamma_da_x(x)
                return
            if event == cv2.EVENT_MOUSEMOVE and self.trascinamento_gamma:
                self._gamma_da_x(x)
                return
            if event == cv2.EVENT_LBUTTONUP and self.trascinamento_gamma:
                self.trascinamento_gamma = False
                return
        # tutto il resto (X, foto, REC, pausa, frecce modalità) come nel v1,
        # ma senza la vecchia zona verticale della gamma
        con_gamma = self.con_gamma
        self.con_gamma = False
        try:
            super().on_mouse(event, x, y, flags, userdata)
        finally:
            self.con_gamma = con_gamma

    # --- VU meter -----------------------------------------------------------
    def _disegna_vu(self, frame):
        """Barra verticale a segmenti: verde in basso, poi giallo, rosso in
        cima; sempre attiva (anche prima della REC), così vedi subito se il
        microfono sente qualcosa. È il livello come finirà nel video."""
        x0, x1 = self.vu_x, self.vu_x + self.vu_larghezza
        y0, y1, n = self.vu_y0, self.vu_y1, self.vu_segmenti
        zona = frame[y0 - 4:y1 + 4, x0 - 4:x1 + 4]
        frame[y0 - 4:y1 + 4, x0 - 4:x1 + 4] = (zona * 0.35).astype(np.uint8)

        attivo = self.microfono is not None and self.microfono.disponibile
        if attivo:
            self.vu.aggiorna(self.microfono.prendi_picco())
            acceso = self.vu.frazione(self.vu.db)
            picco = self.vu.frazione(self.vu.picco_db)
        else:
            acceso = picco = 0.0

        passo = (y1 - y0) / n
        for i in range(n):  # i = 0 in basso
            ya = int(y1 - (i + 1) * passo) + 1
            yb = int(y1 - i * passo) - 1
            db_segmento = VU_MIN_DB + (i + 0.5) / n * -VU_MIN_DB
            if db_segmento >= VU_ROSSO_DB:
                colore = (40, 40, 255)
            elif db_segmento >= VU_GIALLO_DB:
                colore = (40, 210, 255)
            else:
                colore = (60, 210, 60)
            if (i + 0.5) / n > acceso:
                colore = tuple(int(c * 0.22) for c in colore)  # LED spento
            cv2.rectangle(frame, (x0, ya), (x1, yb), colore, -1)
        if attivo and picco > 0.02:  # tacca del picco, bianca
            yp = int(y1 - picco * (y1 - y0))
            cv2.line(frame, (x0 - 2, yp), (x1 + 2, yp), (255, 255, 255), 1)

        etichetta = "MIC" if attivo else "NO MIC"
        colore_testo = (220, 220, 220) if attivo else (60, 60, 255)
        cv2.putText(frame, etichetta, (x0 - 4, y0 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.35, colore_testo, 1, cv2.LINE_AA)

    def chiudi(self):
        super().chiudi()  # salva la clip in corso (e avvia l'unione con l'audio)
        if self.microfono is not None:
            self.microfono.chiudi()

    def _disegna_selettore_modo(self, frame):
        r = self.raggio_freccia
        y = self.y_modo
        x0, x1 = self.x_freccia_sx - r - 8, self.x_freccia_dx + r + 8
        y0, y1 = y - r - 6, y + r + 6
        # fascia scura semitrasparente, così si legge su qualunque immagine
        zona = frame[y0:y1, x0:x1]
        frame[y0:y1, x0:x1] = (zona * 0.45).astype(np.uint8)

        bianco = (255, 255, 255)
        for x, verso in ((self.x_freccia_sx, -1), (self.x_freccia_dx, +1)):
            cv2.circle(frame, (x, y), r, bianco, 2, cv2.LINE_AA)
            punta = np.array([[x + 7 * verso, y], [x - 5 * verso, y - 8], [x - 5 * verso, y + 8]])
            cv2.fillPoly(frame, [punta], bianco, cv2.LINE_AA)

        n = self.stato_modo["modalita"]
        testo = f"MODO {n}"
        nome = self.nomi_modo.get(n)
        if nome:
            testo += f"  {nome}"
        (w, h), _ = cv2.getTextSize(testo, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.putText(frame, testo, (self.x_modo_centro - w // 2, y + h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, bianco, 1, cv2.LINE_AA)

    def gestisci_frame(self, frame_bgr_pulito):
        self.registrazione.scrivi_se_attiva(frame_bgr_pulito)
        if self.richiesta_foto:
            salva_foto_v2(frame_bgr_pulito)
            self.richiesta_foto = False
