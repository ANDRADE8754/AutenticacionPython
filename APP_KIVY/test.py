from kivy.app import App
from kivy.uix.camera import Camera

class TestApp(App):
    def build(self):
        return Camera(play=True)

TestApp().run()