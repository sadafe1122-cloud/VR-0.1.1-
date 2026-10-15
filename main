from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.camera import Camera
from kivy.graphics import Rectangle, Color, Line, ScissorPush, ScissorPop
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform

if platform != 'android':
    Window.size = (900, 500)  # desktop testing only

# ---------------------------------------------------------------- theme
BLACK = (0.04, 0.04, 0.04, 1)
DARK_RED = (0.55, 0.05, 0.07, 1)
DARK_RED_PRESSED = (0.75, 0.08, 0.10, 1)
TEXT = (0.95, 0.90, 0.90, 1)

# Android constants
SCREEN_ORIENTATION_SENSOR_LANDSCAPE = 6   # landscape, but follows 180 deg flips
ROTATION_270 = 3                          # Surface.ROTATION_270


# ------------------------------------------------------- android helpers
def lock_sensor_landscape():
    """Landscape only. If the phone is turned 180 deg the screen flips with it,
    so the picture is never upside down and never switches to portrait."""
    if platform != 'android':
        return
    try:
        from jnius import autoclass
        from android.runnable import run_on_ui_thread

        @run_on_ui_thread
        def _lock():
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            activity.setRequestedOrientation(SCREEN_ORIENTATION_SENSOR_LANDSCAPE)

        _lock()
    except Exception as e:
        print('Orientation lock failed:', e)


def get_display_rotation():
    if platform != 'android':
        return 1
    try:
        from jnius import autoclass
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        return activity.getWindowManager().getDefaultDisplay().getRotation()
    except Exception:
        return 1


def get_camera_count():
    if platform != 'android':
        return 2
    try:
        from jnius import autoclass
        return max(1, autoclass('android.hardware.Camera').getNumberOfCameras())
    except Exception:
        return 4


# ------------------------------------------------------------ UI helpers
def styled_button(text, **kw):
    return Button(text=text, background_normal='', background_down='',
                  background_color=DARK_RED, color=TEXT, **kw)


def styled_label(text, **kw):
    return Label(text=text, color=TEXT, **kw)


class SettingsPanel(BoxLayout):
    def __init__(self, vr, **kwargs):
        self.vr = vr
        super().__init__(orientation='vertical', padding=14, spacing=8,
                         size_hint=(0.72, 0.94),
                         pos_hint={'center_x': 0.5, 'center_y': 0.5}, **kwargs)
        self.vr = vr

        with self.canvas.before:
            Color(*BLACK)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            Color(*DARK_RED)
            self._border = Line(rectangle=(*self.pos, *self.size), width=2)
        self.bind(pos=self._redraw, size=self._redraw)

        self.add_widget(styled_label('SETTINGS', bold=True, font_size='20sp',
                                     size_hint_y=None, height=32))

        # --- camera selector
        row = BoxLayout(size_hint_y=None, height=44, spacing=8)
        prev_btn = styled_button('<', size_hint_x=None, width=60)
        next_btn = styled_button('>', size_hint_x=None, width=60)
        self.cam_label = styled_label('')
        prev_btn.bind(on_release=lambda *_: self.change_camera(-1))
        next_btn.bind(on_release=lambda *_: self.change_camera(+1))
        row.add_widget(prev_btn)
        row.add_widget(self.cam_label)
        row.add_widget(next_btn)
        self.add_widget(row)
        self.add_widget(styled_label(
            'Tip: the wide camera is usually one of the other camera numbers.',
            font_size='12sp', size_hint_y=None, height=20))

        # --- image size
        self.size_label = styled_label('', size_hint_y=None, height=24)
        self.add_widget(self.size_label)
        self.size_slider = self._slider(0.5, 1.5, vr.size_scale, self.change_size)
        self.add_widget(self.size_slider)

        # --- gap
        self.gap_label = styled_label('', size_hint_y=None, height=24)
        self.add_widget(self.gap_label)
        self.gap_slider = self._slider(0, 300, vr.gap, self.change_gap)
        self.add_widget(self.gap_slider)

        # --- manual flip
        self.flip_btn = styled_button('', size_hint_y=None, height=40)
        self.flip_btn.bind(on_release=self.toggle_flip)
        self.add_widget(self.flip_btn)

        self.add_widget(styled_label('Experimental Version', italic=True,
                                     size_hint_y=None, height=26))

        close_btn = styled_button('CLOSE', size_hint_y=None, height=44)
        close_btn.bind(on_release=lambda *_: vr.close_settings())
        self.add_widget(close_btn)

        self.refresh_labels()

    def _slider(self, lo, hi, value, callback):
        s = Slider(min=lo, max=hi, value=value, size_hint_y=None, height=34,
                   value_track=True, value_track_color=DARK_RED,
                   cursor_size=(26, 26))
        s.bind(value=callback)
        return s

    def _redraw(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        self._border.rectangle = (*self.pos, *self.size)

    def refresh_labels(self):
        vr = self.vr
        self.cam_label.text = 'Camera: %d' % vr.cam_index
        self.size_label.text = 'Image size: %d%%' % round(vr.size_scale * 100)
        self.gap_label.text = 'Gap between images: %d px' % round(vr.gap)
        self.flip_btn.text = 'Rotate image 180: %s' % ('ON' if vr.manual_flip else 'OFF')

    def change_camera(self, step):
        self.vr.set_camera((self.vr.cam_index + step) % self.vr.cam_count)
        self.refresh_labels()

    def change_size(self, _inst, value):
        self.vr.size_scale = value
        self.refresh_labels()

    def change_gap(self, _inst, value):
        self.vr.gap = value
        self.refresh_labels()

    def toggle_flip(self, *_):
        self.vr.manual_flip = not self.vr.manual_flip
        self.refresh_labels()

    def on_touch_down(self, touch):
        super().on_touch_down(touch)
        return self.collide_point(*touch.pos)  # swallow touches inside the panel

    def on_touch_move(self, touch):
        super().on_touch_move(touch)
        return self.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        super().on_touch_up(touch)
        return self.collide_point(*touch.pos)


# ------------------------------------------------------------- main view
class VRWidget(FloatLayout):
    HIDE_DELAY = 3  # seconds

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # settings values
        self.cam_index = 0
        self.cam_count = get_camera_count()
        self.size_scale = 1.0
        self.gap = 0.0
        self.manual_flip = False
        self.camera = None
        self.panel = None

        # hidden menu button (top-right corner)
        self.menu_btn = styled_button('MENU', size_hint=(None, None),
                                      size=(90, 44),
                                      pos_hint={'right': 0.99, 'top': 0.98})
        self.menu_btn.opacity = 0
        self.menu_btn.disabled = True
        self.menu_btn.bind(on_release=lambda *_: self.open_settings())
        self.add_widget(self.menu_btn)
        self._hide_event = None

        Clock.schedule_interval(self.update_vr, 1 / 30)

    # ---- camera
    def start_camera(self, *_):
        if self.camera is not None:
            return
        self.camera = Camera(index=self.cam_index, resolution=(640, 480),
                             play=True, size_hint=(None, None), size=(1, 1))
        self.camera.opacity = 0
        self.add_widget(self.camera, index=len(self.children))

    def set_camera(self, index):
        self.cam_index = index
        if self.camera is None:
            return
        self.camera.play = False
        self.camera.index = index
        self.camera.play = True

    # ---- hidden menu button
    def on_touch_down(self, touch):
        if self.panel is not None:           # settings open: panel handles it
            return super().on_touch_down(touch)
        if self.menu_btn.disabled:           # first touch only reveals the button
            self.show_menu_button()
            return True
        self.show_menu_button()              # keep it alive while touching
        return super().on_touch_down(touch)

    def show_menu_button(self):
        self.menu_btn.disabled = False
        Animation.cancel_all(self.menu_btn, 'opacity')
        Animation(opacity=1, duration=0.15).start(self.menu_btn)
        if self._hide_event:
            self._hide_event.cancel()
        self._hide_event = Clock.schedule_once(self.hide_menu_button, self.HIDE_DELAY)

    def hide_menu_button(self, *_):
        anim = Animation(opacity=0, duration=0.4)
        anim.bind(on_complete=lambda *_: setattr(self.menu_btn, 'disabled', True))
        Animation.cancel_all(self.menu_btn, 'opacity')
        anim.start(self.menu_btn)

    # ---- settings
    def open_settings(self):
        if self.panel is not None:
            return
        if self._hide_event:
            self._hide_event.cancel()
        self.menu_btn.opacity = 0
        self.menu_btn.disabled = True
        self.panel = SettingsPanel(self)
        self.add_widget(self.panel)

    def close_settings(self):
        if self.panel is not None:
            self.remove_widget(self.panel)
            self.panel = None

    # ---- drawing
    def update_vr(self, dt):
        if self.camera is None or not self.camera.texture:
            return
        tex = self.camera.texture
        w, h = Window.width, Window.height
        half_w = w / 2.0
        gap = self.gap
        cell_w = half_w - gap / 2.0

        # Android reports 270 when the phone is in the "other" landscape.
        # In that case the camera image must be turned 180 deg to stay upright.
        flip = (get_display_rotation() == ROTATION_270) != self.manual_flip

        tc = list(tex.tex_coords)
        if flip:
            tc = tc[4:] + tc[:4]  # 180 degree rotation of the texture

        tw, th = tex.size
        fit = min(cell_w / float(tw), h / float(th)) * self.size_scale
        iw, ih = tw * fit, th * fit

        self.canvas.before.clear()
        with self.canvas.before:
            Color(0, 0, 0, 1)
            Rectangle(pos=(0, 0), size=(w, h))
            Color(1, 1, 1, 1)
            for cell_x in (0, half_w + gap / 2.0):
                ScissorPush(x=int(cell_x), y=0, width=int(cell_w), height=int(h))
                Rectangle(texture=tex, tex_coords=tc,
                          pos=(cell_x + (cell_w - iw) / 2.0, (h - ih) / 2.0),
                          size=(iw, ih))
                ScissorPop()


class VRApp(App):
    def build(self):
        self.vr = VRWidget()
        return self.vr

    def on_start(self):
        lock_sensor_landscape()
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission

                def _done(permissions, results):
                    Clock.schedule_once(self.vr.start_camera)

                request_permissions([Permission.CAMERA], _done)
                return
            except Exception as e:
                # Pydroid 3 does not support this API; the camera permission
                # must be granted to Pydroid in the phone's app settings.
                print('Permission request unavailable:', e)
        Clock.schedule_once(self.vr.start_camera, 0.5)


if __name__ == '__main__':
    VRApp().run()
