import os
import json
from datetime import datetime
from threading import Thread

from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Line

from kivymd.app import MDApp
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.dialog import MDDialog, MDDialogHeadlineText, MDDialogSupportingText
from kivymd.uix.card import MDCard

try:
    from kivymd.uix.topappbar import MDTopAppBar
except ModuleNotFoundError:
    try:
        from kivymd.uix.toolbar import MDTopAppBar
    except ModuleNotFoundError:
        MDTopAppBar = None

import cv2
import sounddevice as sd
from scipy.io.wavfile import write


class ModernCard(MDCard):
    """Tarjeta moderna con sombra y esquinas redondeadas"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.elevation = 2
        self.padding = dp(20)
        self.spacing = dp(12)
        self.radius = [dp(16)]
        self.md_bg_color = (0.12, 0.12, 0.18, 1)  # Fondo oscuro elegante


class RecordingIndicator(MDBoxLayout):
    """Indicador visual de grabación con animación de onda"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint = (1, None)
        self.height = dp(100)
        self.padding = dp(20)
        self.spacing = dp(10)
        
        # Label de estado
        self.status_label = MDLabel(
            text="🎙️ GRABANDO...",
            halign="center",
            theme_text_color="Custom",
            text_color=(1, 0.3, 0.3, 1),
            font_style="Headline",
            role="small"
        )
        self.add_widget(self.status_label)
        
        # Contenedor para las barras de audio
        self.wave_container = MDBoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(40),
            spacing=dp(4),
            padding=[dp(50), 0]
        )
        
        # Crear 5 barras animadas
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
        
        # Iniciar animación
        self.animation_event = None
        self.start_animation()
    
    def _update_bar(self, instance, value):
        """Actualiza la posición de las barras"""
        for i, bar in enumerate(self.bars):
            container = self.wave_container.children[len(self.bars) - 1 - i]
            bar.pos = container.pos
            bar.size = (container.width, bar.size[1])
    
    def animate_bar(self, bar_index, *args):
        """Anima una barra individual"""
        if bar_index < len(self.bars):
            bar = self.bars[bar_index]
            # Altura aleatoria para simular onda de audio
            from random import uniform
            new_height = dp(uniform(10, 35))
            
            # Animación suave
            anim = Animation(size=(bar.size[0], new_height), duration=0.3)
            anim.start(bar)
    
    def start_animation(self):
        """Inicia la animación de las barras"""
        for i in range(len(self.bars)):
            Clock.schedule_interval(
                lambda dt, idx=i: self.animate_bar(idx),
                0.15 * (i + 1)
            )
    
    def stop_animation(self):
        """Detiene todas las animaciones"""
        Clock.unschedule(self.animate_bar)


class RegistroScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Layout principal con fondo degradado
        main_layout = MDBoxLayout(orientation="vertical")
        
        # Fondo con color sólido oscuro
        with main_layout.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            self.bg_rect = RoundedRectangle(pos=main_layout.pos, size=main_layout.size)
        main_layout.bind(pos=self._update_bg, size=self._update_bg)
        
        # Header moderno
        header = MDBoxLayout(
            size_hint_y=None,
            height=dp(80),
            padding=[dp(20), dp(10)],
            spacing=dp(10)
        )
        
        # Título con estilo
        title_label = MDLabel(
            text="🔐 Registro Biométrico",
            font_style="Display",
            role="small",
            halign="left",
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1)
        )
        header.add_widget(title_label)
        main_layout.add_widget(header)
        
        # Contenedor scrollable
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
            text="📋 Información Personal",
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
            size_hint_x=1,
            theme_line_color="Custom",
            line_color_normal=(0.3, 0.5, 0.8, 0.5),
            line_color_focus=(0.6, 0.8, 1, 1)
        )
        info_card.add_widget(self.nombre_input)
        
        btn_crear = MDButton(
            style="elevated",
            pos_hint={"center_x": 0.5},
            size_hint=(1, None),
            height=dp(48)
        )
        btn_crear.md_bg_color = (0.2, 0.6, 0.9, 1)
        btn_crear.add_widget(MDButtonText(text="✨ Crear Perfil"))
        btn_crear.bind(on_release=self.crear_persona)
        info_card.add_widget(btn_crear)
        
        content_layout.add_widget(info_card)
        
        # Tarjeta de captura facial
        face_card = ModernCard(orientation="vertical", size_hint_y=None, height=dp(140))
        
        face_title = MDLabel(
            text="📸 Reconocimiento Facial",
            font_style="Title",
            role="medium",
            size_hint_y=None,
            height=dp(30),
            theme_text_color="Custom",
            text_color=(0.6, 1, 0.8, 1)
        )
        face_card.add_widget(face_title)
        
        face_desc = MDLabel(
            text="Captura tu rostro para identificación",
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
        btn_foto.add_widget(MDButtonText(text="📷 Tomar Fotografía"))
        btn_foto.bind(on_release=self.tomar_foto)
        face_card.add_widget(btn_foto)
        
        content_layout.add_widget(face_card)
        
        # Tarjeta de captura de voz
        voice_card = ModernCard(orientation="vertical", size_hint_y=None, height=dp(140))
        
        voice_title = MDLabel(
            text="🎤 Reconocimiento de Voz",
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
        btn_audio.add_widget(MDButtonText(text="🎙️ Grabar Audio"))
        btn_audio.bind(on_release=self.grabar_audio)
        voice_card.add_widget(btn_audio)
        
        content_layout.add_widget(voice_card)
        
        # Indicador de grabación (inicialmente oculto)
        self.recording_indicator = RecordingIndicator()
        self.recording_indicator.opacity = 0
        self.recording_indicator.size_hint_y = None
        self.recording_indicator.height = 0
        content_layout.add_widget(self.recording_indicator)
        
        main_layout.add_widget(content_layout)
        self.add_widget(main_layout)
    
    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
    
    def crear_persona(self, instance):
        nombre = self.nombre_input.text.strip()
        if not nombre:
            self._mostrar_dialogo("❌ Error", "Por favor ingresa un nombre válido.", "error")
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
        
        self._mostrar_dialogo("✅ Éxito", f"Perfil creado exitosamente para:\n{nombre}", "success")
    
    def tomar_foto(self, instance):
        nombre = self.nombre_input.text.strip()
        if not nombre:
            self._mostrar_dialogo("⚠️ Advertencia", "Primero debes crear un perfil.", "warning")
            return
        
        ruta = f"dataset/{nombre}/face"
        os.makedirs(ruta, exist_ok=True)
        
        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        ret, frame = cam.read()
        if ret:
            archivo = f"{ruta}/foto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            cv2.imwrite(archivo, frame)
            self._mostrar_dialogo("📸 Capturado", "Fotografía guardada correctamente.", "success")
        else:
            self._mostrar_dialogo("❌ Error", "No se pudo acceder a la cámara.", "error")
        cam.release()
    
    def grabar_audio(self, instance):
        nombre = self.nombre_input.text.strip()
        if not nombre:
            self._mostrar_dialogo("⚠️ Advertencia", "Primero debes crear un perfil.", "warning")
            return
        
        # Mostrar indicador de grabación
        self.show_recording_indicator()
        
        # Ejecutar grabación en hilo separado
        Thread(target=self._grabar_audio_thread, args=(nombre,)).start()
    
    def _grabar_audio_thread(self, nombre):
        """Grabación en hilo separado para no bloquear UI"""
        ruta = f"dataset/{nombre}/voice"
        os.makedirs(ruta, exist_ok=True)
        
        duracion = 3
        frecuencia = 44100
        
        try:
            audio = sd.rec(int(duracion * frecuencia), samplerate=frecuencia, channels=1, dtype="int16")
            sd.wait()
            archivo = f"{ruta}/voz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            write(archivo, frecuencia, audio)
            
            # Ocultar indicador y mostrar éxito
            Clock.schedule_once(lambda dt: self.hide_recording_indicator(), 0)
            Clock.schedule_once(
                lambda dt: self._mostrar_dialogo("🎤 Grabado", "Audio guardado correctamente.", "success"),
                0
            )
        except Exception as e:
            Clock.schedule_once(lambda dt: self.hide_recording_indicator(), 0)
            Clock.schedule_once(
                lambda dt: self._mostrar_dialogo("❌ Error", f"Error al grabar: {str(e)}", "error"),
                0
            )
    
    def show_recording_indicator(self):
        """Muestra el indicador de grabación con animación"""
        self.recording_indicator.height = dp(100)
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
        btn_ok.add_widget(MDButtonText(text="Entendido"))
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