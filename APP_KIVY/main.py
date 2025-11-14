import os
import json
from datetime import datetime
from threading import Thread

from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.graphics.texture import Texture
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView

from kivymd.app import MDApp
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.dialog import MDDialog, MDDialogHeadlineText, MDDialogSupportingText, MDDialogContentContainer
from kivymd.uix.card import MDCard
from kivymd.uix.list import MDListItem, MDListItemLeadingIcon, MDListItemHeadlineText, MDListItemSupportingText, MDListItemTertiaryText

import cv2
import sounddevice as sd
from scipy.io.wavfile import write, read
import numpy as np


class CameraPreview(MDBoxLayout):
    """Vista previa de la cámara con controles"""
    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.orientation = 'vertical'
        self.padding = dp(20)
        self.spacing = dp(15)
        self.size_hint = (1, 1)
        
        # Título
        title = MDLabel(
            text="VISTA PREVIA DE CAMARA",
            font_style="Headline",
            role="small",
            halign="center",
            size_hint_y=None,
            height=dp(40),
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1)
        )
        self.add_widget(title)
        
        # Contenedor de la imagen
        self.camera_image = Image(
            size_hint=(1, 0.7),
            allow_stretch=True,
            keep_ratio=True
        )
        self.add_widget(self.camera_image)
        
        # Instrucciones
        instructions = MDLabel(
            text="Centra tu rostro y presiona CAPTURAR",
            font_style="Body",
            role="small",
            halign="center",
            size_hint_y=None,
            height=dp(30),
            theme_text_color="Custom",
            text_color=(0.7, 0.7, 0.7, 1)
        )
        self.add_widget(instructions)
        
        # Botones de control
        btn_layout = MDBoxLayout(
            orientation='horizontal',
            spacing=dp(10),
            size_hint_y=None,
            height=dp(60)
        )
        
        # Botón Cancelar
        btn_cancel = MDButton(style="elevated", size_hint=(0.5, 1))
        btn_cancel.md_bg_color = (0.6, 0.3, 0.3, 1)
        btn_cancel.add_widget(MDButtonText(text="CANCELAR"))
        btn_cancel.bind(on_release=lambda x: self.callback(None))
        btn_layout.add_widget(btn_cancel)
        
        # Botón Capturar
        btn_capture = MDButton(style="elevated", size_hint=(0.5, 1))
        btn_capture.md_bg_color = (0.2, 0.8, 0.6, 1)
        btn_capture.add_widget(MDButtonText(text="CAPTURAR"))
        btn_capture.bind(on_release=lambda x: self.callback(self.current_frame))
        btn_layout.add_widget(btn_capture)
        
        self.add_widget(btn_layout)
        
        self.capture = None
        self.current_frame = None
        self.update_event = None
        
        Clock.schedule_once(lambda dt: self.start_camera(), 0.5)
    
    def start_camera(self):
        try:
            self.capture = cv2.VideoCapture(0)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.update_event = Clock.schedule_interval(self.update_frame, 1.0 / 30.0)
        except Exception as e:
            print(f"Error al iniciar cámara: {e}")
    
    def update_frame(self, dt):
        if self.capture is None:
            return
        
        ret, frame = self.capture.read()
        if ret:
            self.current_frame = frame.copy()
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_rgb = cv2.flip(frame_rgb, 1)
            
            buf = frame_rgb.tobytes()
            texture = Texture.create(
                size=(frame_rgb.shape[1], frame_rgb.shape[0]),
                colorfmt='rgb'
            )
            texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
            texture.flip_vertical()
            self.camera_image.texture = texture
    
    def stop_camera(self):
        if self.update_event:
            self.update_event.cancel()
        if self.capture:
            self.capture.release()
            self.capture = None


class RecordingIndicator(MDBoxLayout):
    """Indicador visual de grabación"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint = (1, None)
        self.height = dp(80)
        self.padding = dp(20)
        self.spacing = dp(10)
        
        self.status_label = MDLabel(
            text="GRABANDO AUDIO...",
            halign="center",
            theme_text_color="Custom",
            text_color=(1, 0.3, 0.3, 1),
            font_style="Headline",
            role="small"
        )
        self.add_widget(self.status_label)
        
        self.wave_container = MDBoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(40),
            spacing=dp(4),
            padding=[dp(50), 0]
        )
        
        self.bars = []
        for i in range(5):
            bar_container = MDBoxLayout(size_hint=(1, 1))
            with bar_container.canvas.before:
                Color(1, 0.3, 0.3, 1)
                bar = RoundedRectangle(
                    pos=bar_container.pos,
                    size=(bar_container.width, dp(10)),
                    radius=[dp(4)]
                )
                self.bars.append(bar)
            bar_container.bind(pos=self._update_bar, size=self._update_bar)
            self.wave_container.add_widget(bar_container)
        
        self.add_widget(self.wave_container)
        self.start_animation()
    
    def _update_bar(self, instance, value):
        for i, bar in enumerate(self.bars):
            container = self.wave_container.children[len(self.bars) - 1 - i]
            bar.pos = container.pos
            bar.size = (container.width, bar.size[1])
    
    def animate_bar(self, bar_index, *args):
        if bar_index < len(self.bars):
            bar = self.bars[bar_index]
            from random import uniform
            new_height = dp(uniform(10, 35))
            anim = Animation(size=(bar.size[0], new_height), duration=0.3)
            anim.start(bar)
    
    def start_animation(self):
        for i in range(len(self.bars)):
            Clock.schedule_interval(
                lambda dt, idx=i: self.animate_bar(idx),
                0.15 * (i + 1)
            )
    
    def stop_animation(self):
        Clock.unschedule(self.animate_bar)


class GalleryItem(MDCard):
    """Item de galería para fotos/audios"""
    def __init__(self, filepath, tipo, delete_callback, **kwargs):
        super().__init__(**kwargs)
        self.filepath = filepath
        self.tipo = tipo
        self.delete_callback = delete_callback
        
        self.orientation = 'vertical'
        self.size_hint = (1, None)
        self.height = dp(280) if tipo == "foto" else dp(120)
        self.padding = dp(10)
        self.spacing = dp(10)
        self.elevation = 2
        self.radius = [dp(12)]
        self.md_bg_color = (0.12, 0.12, 0.18, 1)
        
        if tipo == "foto":
            # Mostrar imagen
            try:
                img = Image(
                    source=filepath,
                    size_hint=(1, None),
                    height=dp(180),
                    allow_stretch=True,
                    keep_ratio=True
                )
                self.add_widget(img)
            except:
                pass
        else:
            # Mostrar info de audio
            audio_label = MDLabel(
                text="ARCHIVO DE AUDIO",
                halign="center",
                font_style="Title",
                role="small",
                size_hint_y=None,
                height=dp(30)
            )
            self.add_widget(audio_label)
        
        # Nombre del archivo
        filename = os.path.basename(filepath)
        name_label = MDLabel(
            text=filename,
            halign="center",
            font_style="Body",
            role="small",
            size_hint_y=None,
            height=dp(25)
        )
        self.add_widget(name_label)
        
        # Botones
        btn_layout = MDBoxLayout(
            orientation='horizontal',
            spacing=dp(10),
            size_hint_y=None,
            height=dp(45)
        )
        
        if tipo == "audio":
            # Botón reproducir
            btn_play = MDButton(style="elevated", size_hint=(0.5, 1))
            btn_play.md_bg_color = (0.2, 0.6, 0.9, 1)
            btn_play.add_widget(MDButtonText(text="REPRODUCIR"))
            btn_play.bind(on_release=lambda x: self.play_audio())
            btn_layout.add_widget(btn_play)
        
        # Botón eliminar
        btn_delete = MDButton(style="elevated", size_hint=(0.5 if tipo == "audio" else 1, 1))
        btn_delete.md_bg_color = (0.9, 0.3, 0.3, 1)
        btn_delete.add_widget(MDButtonText(text="ELIMINAR"))
        btn_delete.bind(on_release=lambda x: self.delete_callback(filepath))
        btn_layout.add_widget(btn_delete)
        
        self.add_widget(btn_layout)
    
    def play_audio(self):
        """Reproduce el archivo de audio"""
        try:
            samplerate, data = read(self.filepath)
            sd.play(data, samplerate)
        except Exception as e:
            print(f"Error al reproducir audio: {e}")


class ModernCard(MDCard):
    """Tarjeta moderna con sombra"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.elevation = 2
        self.padding = dp(20)
        self.spacing = dp(12)
        self.radius = [dp(16)]
        self.md_bg_color = (0.12, 0.12, 0.18, 1)


class RegistroScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        main_layout = MDBoxLayout(orientation="vertical")
        
        with main_layout.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            self.bg_rect = RoundedRectangle(pos=main_layout.pos, size=main_layout.size)
        main_layout.bind(pos=self._update_bg, size=self._update_bg)
        
        # Header
        header = MDBoxLayout(
            size_hint_y=None,
            height=dp(80),
            padding=[dp(20), dp(10)],
            spacing=dp(10)
        )
        
        title_label = MDLabel(
            text="REGISTRO BIOMETRICO",
            font_style="Display",
            role="small",
            halign="left",
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1)
        )
        header.add_widget(title_label)
        
        # Botón ver personas
        btn_ver = MDButton(
            style="elevated",
            size_hint=(None, None),
            width=dp(150),
            height=dp(48)
        )
        btn_ver.md_bg_color = (0.5, 0.3, 0.8, 1)
        btn_ver.add_widget(MDButtonText(text="VER PERSONAS"))
        btn_ver.bind(on_release=self.ver_personas)
        header.add_widget(btn_ver)
        
        main_layout.add_widget(header)
        
        # Scroll view para el contenido
        scroll = ScrollView(size_hint=(1, 1))
        content_layout = MDBoxLayout(
            orientation="vertical",
            padding=dp(20),
            spacing=dp(20),
            size_hint_y=None
        )
        content_layout.bind(minimum_height=content_layout.setter('height'))
        
        # Tarjeta de información personal
        info_card = ModernCard(orientation="vertical", size_hint_y=None, height=dp(160))
        
        info_title = MDLabel(
            text="INFORMACION PERSONAL",
            font_style="Title",
            role="medium",
            size_hint_y=None,
            height=dp(30),
            theme_text_color="Custom",
            text_color=(0.6, 0.8, 1, 1)
        )
        info_card.add_widget(info_title)
        
        self.nombre_input = MDTextField(
            hint_text="Nombre completo",
            mode="filled",
            size_hint_x=1
        )
        info_card.add_widget(self.nombre_input)
        
        btn_crear = MDButton(
            style="elevated",
            pos_hint={"center_x": 0.5},
            size_hint=(1, None),
            height=dp(48)
        )
        btn_crear.md_bg_color = (0.2, 0.6, 0.9, 1)
        btn_crear.add_widget(MDButtonText(text="CREAR PERFIL"))
        btn_crear.bind(on_release=self.crear_persona)
        info_card.add_widget(btn_crear)
        
        content_layout.add_widget(info_card)
        
        # Tarjeta de captura facial
        face_card = ModernCard(orientation="vertical", size_hint_y=None, height=dp(140))
        
        face_title = MDLabel(
            text="RECONOCIMIENTO FACIAL",
            font_style="Title",
            role="medium",
            size_hint_y=None,
            height=dp(30),
            theme_text_color="Custom",
            text_color=(0.6, 1, 0.8, 1)
        )
        face_card.add_widget(face_title)
        
        face_desc = MDLabel(
            text="Captura tu rostro para identificacion",
            font_style="Body",
            role="small",
            size_hint_y=None,
            height=dp(20),
            theme_text_color="Custom",
            text_color=(0.7, 0.7, 0.7, 1)
        )
        face_card.add_widget(face_desc)
        
        btn_foto = MDButton(
            style="elevated",
            pos_hint={"center_x": 0.5},
            size_hint=(1, None),
            height=dp(48)
        )
        btn_foto.md_bg_color = (0.2, 0.8, 0.6, 1)
        btn_foto.add_widget(MDButtonText(text="TOMAR FOTOGRAFIA"))
        btn_foto.bind(on_release=self.tomar_foto)
        face_card.add_widget(btn_foto)
        
        content_layout.add_widget(face_card)
        
        # Tarjeta de captura de voz
        voice_card = ModernCard(orientation="vertical", size_hint_y=None, height=dp(140))
        
        voice_title = MDLabel(
            text="RECONOCIMIENTO DE VOZ",
            font_style="Title",
            role="medium",
            size_hint_y=None,
            height=dp(30),
            theme_text_color="Custom",
            text_color=(1, 0.7, 0.6, 1)
        )
        voice_card.add_widget(voice_title)
        
        voice_desc = MDLabel(
            text="Graba tu voz durante 3 segundos",
            font_style="Body",
            role="small",
            size_hint_y=None,
            height=dp(20),
            theme_text_color="Custom",
            text_color=(0.7, 0.7, 0.7, 1)
        )
        voice_card.add_widget(voice_desc)
        
        btn_audio = MDButton(
            style="elevated",
            pos_hint={"center_x": 0.5},
            size_hint=(1, None),
            height=dp(48)
        )
        btn_audio.md_bg_color = (0.9, 0.4, 0.5, 1)
        btn_audio.add_widget(MDButtonText(text="GRABAR AUDIO"))
        btn_audio.bind(on_release=self.grabar_audio)
        voice_card.add_widget(btn_audio)
        
        content_layout.add_widget(voice_card)
        
        # Indicador de grabación
        self.recording_indicator = RecordingIndicator()
        self.recording_indicator.opacity = 0
        self.recording_indicator.size_hint_y = None
        self.recording_indicator.height = 0
        content_layout.add_widget(self.recording_indicator)
        
        # Botón ver galería
        btn_galeria = MDButton(
            style="elevated",
            pos_hint={"center_x": 0.5},
            size_hint=(0.9, None),
            height=dp(48)
        )
        btn_galeria.md_bg_color = (0.8, 0.5, 0.2, 1)
        btn_galeria.add_widget(MDButtonText(text="VER GALERIA"))
        btn_galeria.bind(on_release=self.ver_galeria)
        content_layout.add_widget(btn_galeria)
        
        scroll.add_widget(content_layout)
        main_layout.add_widget(scroll)
        self.add_widget(main_layout)
        
        self.camera_preview = None
        self.camera_dialog = None
    
    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
    
    def persona_existe(self, nombre):
        """Verifica si la persona ya existe"""
        return os.path.exists(f"dataset/{nombre}/metadata.json")
    
    def crear_persona(self, instance):
        nombre = self.nombre_input.text.strip()
        if not nombre:
            self._mostrar_dialogo("ERROR", "Por favor ingresa un nombre valido.", "error")
            return
        
        if self.persona_existe(nombre):
            self._mostrar_dialogo("ADVERTENCIA", f"La persona '{nombre}' ya existe.", "warning")
            return
        
        ruta = f"dataset/{nombre}"
        os.makedirs(f"{ruta}/face", exist_ok=True)
        os.makedirs(f"{ruta}/voice", exist_ok=True)
        
        meta = {
            "id": nombre,
            "nombre": nombre,
            "frase_clave": "Acceso autorizado",
            "fecha_registro": datetime.now().isoformat(),
        }
        
        with open(f"{ruta}/metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=4, ensure_ascii=False)
        
        self._mostrar_dialogo("EXITO", f"Perfil creado exitosamente para:\n{nombre}", "success")
    
    def tomar_foto(self, instance):
        nombre = self.nombre_input.text.strip()
        if not nombre:
            self._mostrar_dialogo("ADVERTENCIA", "Primero debes ingresar un nombre.", "warning")
            return
        
        if not self.persona_existe(nombre):
            self._mostrar_dialogo("ERROR", f"La persona '{nombre}' no existe. Crea el perfil primero.", "error")
            return
        
        self.camera_preview = CameraPreview(callback=self.on_camera_callback)
        self.camera_dialog = MDDialog()
        self.camera_dialog.add_widget(self.camera_preview)
        self.camera_dialog.open()
    
    def on_camera_callback(self, frame):
        if self.camera_preview:
            self.camera_preview.stop_camera()
        
        if self.camera_dialog:
            self.camera_dialog.dismiss()
        
        if frame is not None:
            nombre = self.nombre_input.text.strip()
            ruta = f"dataset/{nombre}/face"
            
            archivo = f"{ruta}/foto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            frame_to_save = cv2.flip(frame, 1)
            cv2.imwrite(archivo, frame_to_save)
            
            self._mostrar_dialogo("CAPTURADO", "Fotografia guardada correctamente.", "success")
    
    def grabar_audio(self, instance):
        nombre = self.nombre_input.text.strip()
        if not nombre:
            self._mostrar_dialogo("ADVERTENCIA", "Primero debes ingresar un nombre.", "warning")
            return
        
        if not self.persona_existe(nombre):
            self._mostrar_dialogo("ERROR", f"La persona '{nombre}' no existe. Crea el perfil primero.", "error")
            return
        
        self.show_recording_indicator()
        Thread(target=self._grabar_audio_thread, args=(nombre,)).start()
    
    def _grabar_audio_thread(self, nombre):
        ruta = f"dataset/{nombre}/voice"
        duracion = 3
        frecuencia = 44100
        
        try:
            audio = sd.rec(int(duracion * frecuencia), samplerate=frecuencia, channels=1, dtype="int16")
            sd.wait()
            archivo = f"{ruta}/voz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            write(archivo, frecuencia, audio)
            
            Clock.schedule_once(lambda dt: self.hide_recording_indicator(), 0)
            Clock.schedule_once(
                lambda dt: self._mostrar_dialogo("GRABADO", "Audio guardado correctamente.", "success"),
                0
            )
        except Exception as e:
            Clock.schedule_once(lambda dt: self.hide_recording_indicator(), 0)
            Clock.schedule_once(
                lambda dt: self._mostrar_dialogo("ERROR", f"Error al grabar: {str(e)}", "error"),
                0
            )
    
    def ver_galeria(self, instance):
        nombre = self.nombre_input.text.strip()
        if not nombre:
            self._mostrar_dialogo("ADVERTENCIA", "Primero debes ingresar un nombre.", "warning")
            return
        
        if not self.persona_existe(nombre):
            self._mostrar_dialogo("ERROR", f"La persona '{nombre}' no existe.", "error")
            return
        
        # Crear contenido del diálogo
        content = MDBoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        
        scroll = ScrollView(size_hint=(1, 1))
        gallery_layout = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            size_hint_y=None,
            padding=dp(5)
        )
        gallery_layout.bind(minimum_height=gallery_layout.setter('height'))
        
        # Obtener fotos
        face_path = f"dataset/{nombre}/face"
        if os.path.exists(face_path):
            fotos = [f for f in os.listdir(face_path) if f.endswith('.jpg')]
            for foto in fotos:
                filepath = os.path.join(face_path, foto)
                item = GalleryItem(filepath, "foto", self.eliminar_archivo)
                gallery_layout.add_widget(item)
        
        # Obtener audios
        voice_path = f"dataset/{nombre}/voice"
        if os.path.exists(voice_path):
            audios = [f for f in os.listdir(voice_path) if f.endswith('.wav')]
            for audio in audios:
                filepath = os.path.join(voice_path, audio)
                item = GalleryItem(filepath, "audio", self.eliminar_archivo)
                gallery_layout.add_widget(item)
        
        scroll.add_widget(gallery_layout)
        content.add_widget(scroll)
        
        dialog = MDDialog(
            MDDialogHeadlineText(text=f"GALERIA DE {nombre.upper()}"),
        )
        dialog.add_widget(content)
        
        btn_close = MDButton(style="text")
        btn_close.add_widget(MDButtonText(text="CERRAR"))
        btn_close.bind(on_release=lambda x: dialog.dismiss())
        dialog.buttons = [btn_close]
        
        dialog.size_hint = (0.9, 0.8)
        dialog.open()
    
    def ver_personas(self, instance):
        """Muestra lista de personas registradas"""
        if not os.path.exists("dataset"):
            self._mostrar_dialogo("INFO", "No hay personas registradas.", "info")
            return
        
        personas = [d for d in os.listdir("dataset") if os.path.isdir(f"dataset/{d}")]
        
        if not personas:
            self._mostrar_dialogo("INFO", "No hay personas registradas.", "info")
            return
        
        content = MDBoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        scroll = ScrollView(size_hint=(1, 1))
        list_layout = MDBoxLayout(
            orientation='vertical',
            spacing=dp(5),
            size_hint_y=None,
            padding=dp(5)
        )
        list_layout.bind(minimum_height=list_layout.setter('height'))
        
        for persona in personas:
            meta_path = f"dataset/{persona}/metadata.json"
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                # Contar fotos y audios
                num_fotos = len([f for f in os.listdir(f"dataset/{persona}/face") if f.endswith('.jpg')])
                num_audios = len([f for f in os.listdir(f"dataset/{persona}/voice") if f.endswith('.wav')])
                
                item_card = MDCard(
                    orientation='vertical',
                    size_hint=(1, None),
                    height=dp(100),
                    padding=dp(15),
                    spacing=dp(5),
                    elevation=2,
                    radius=[dp(10)]
                )
                item_card.md_bg_color = (0.12, 0.12, 0.18, 1)
                
                name_label = MDLabel(
                    text=persona,
                    font_style="Title",
                    role="medium",
                    size_hint_y=None,
                    height=dp(30)
                )
                item_card.add_widget(name_label)
                
                info_label = MDLabel(
                    text=f"Fotos: {num_fotos} | Audios: {num_audios}",
                    font_style="Body",
                    role="small",
                    size_hint_y=None,
                    height=dp(25),
                    theme_text_color="Custom",
                    text_color=(0.7, 0.7, 0.7, 1)
                )
                item_card.add_widget(info_label)
                
                fecha = meta.get('fecha_registro', 'N/A')[:10]
                date_label = MDLabel(
                    text=f"Registrado: {fecha}",
                    font_style="Body",
                    role="small",
                    size_hint_y=None,
                    height=dp(20),
                    theme_text_color="Custom",
                    text_color=(0.5, 0.5, 0.5, 1)
                )
                item_card.add_widget(date_label)
                
                list_layout.add_widget(item_card)
        
        scroll.add_widget(list_layout)
        content.add_widget(scroll)
        
        dialog = MDDialog(
            MDDialogHeadlineText(text="PERSONAS REGISTRADAS"),
        )
        dialog.add_widget(content)
        
        btn_close = MDButton(style="text")
        btn_close.add_widget(MDButtonText(text="CERRAR"))
        btn_close.bind(on_release=lambda x: dialog.dismiss())
        dialog.buttons = [btn_close]
        
        dialog.size_hint = (0.8, 0.7)
        dialog.open()
    
    def eliminar_archivo(self, filepath):
        """Elimina un archivo (foto o audio)"""
        def confirmar_eliminacion(instance):
            try:
                os.remove(filepath)
                confirm_dialog.dismiss()
                self._mostrar_dialogo("ELIMINADO", "Archivo eliminado correctamente.", "success")
            except Exception as e:
                confirm_dialog.dismiss()
                self._mostrar_dialogo("ERROR", f"No se pudo eliminar: {str(e)}", "error")
        
        confirm_dialog = MDDialog(
            MDDialogHeadlineText(text="CONFIRMAR ELIMINACION"),
            MDDialogSupportingText(text=f"¿Estas seguro de eliminar este archivo?\n{os.path.basename(filepath)}"),
        )
        
        btn_cancel = MDButton(style="text")
        btn_cancel.add_widget(MDButtonText(text="CANCELAR"))
        btn_cancel.bind(on_release=lambda x: confirm_dialog.dismiss())
        
        btn_confirm = MDButton(style="text")
        btn_confirm.md_bg_color = (0.9, 0.3, 0.3, 1)
        btn_confirm.add_widget(MDButtonText(text="ELIMINAR"))
        btn_confirm.bind(on_release=confirmar_eliminacion)
        
        confirm_dialog.buttons = [btn_cancel, btn_confirm]
        confirm_dialog.open()
    
    def show_recording_indicator(self):
        """Muestra el indicador de grabación con animación"""
        self.recording_indicator.height = dp(80)
        anim = Animation(opacity=1, duration=0.3)
        anim.start(self.recording_indicator)
    
    def hide_recording_indicator(self):
        """Oculta el indicador de grabación con animación"""
        anim = Animation(opacity=0, duration=0.3)
        anim.bind(on_complete=lambda *args: setattr(self.recording_indicator, 'height', 0))
        anim.start(self.recording_indicator)
    
    def _mostrar_dialogo(self, titulo, texto, tipo="info"):
        """Muestra diálogo con colores según el tipo"""
        colores = {
            "success": (0.2, 0.8, 0.6, 1),
            "error": (0.9, 0.3, 0.3, 1),
            "warning": (1, 0.7, 0.2, 1),
            "info": (0.6, 0.8, 1, 1)
        }
        
        dialog = MDDialog(
            MDDialogHeadlineText(text=titulo),
            MDDialogSupportingText(text=texto),
        )
        
        btn_ok = MDButton(style="text")
        btn_ok.md_bg_color = colores.get(tipo, colores["info"])
        btn_ok.add_widget(MDButtonText(text="ENTENDIDO"))
        btn_ok.bind(on_release=lambda inst: dialog.dismiss())
        
        dialog.buttons = [btn_ok]
        dialog.open()


class RecolectorApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        
        sm = ScreenManager()
        sm.add_widget(RegistroScreen(name="registro"))
        return sm


if __name__ == "__main__":
    RecolectorApp().run()