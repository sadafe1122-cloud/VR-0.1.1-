from kivy.config import Config
Config.set('graphics', 'maxfps', '60')

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.camera import Camera
from kivy.graphics import Rectangle, Color, Line, ScissorPush, ScissorPop
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.utils import platform

if platform != 'android':
    Window.size = (1000, 500)  # desktop testing only

# ---------------------------------------------------------------- theme
BLACK = (0.04, 0.04, 0.04, 1)
DARK_RED = (0.55, 0.05, 0.07, 1)
TEXT = (0.95, 0.90, 0.90, 1)

# Android constants
ORIENT_SENSOR_LANDSCAPE = 6   # landscape, follows 180 degree flips
ORIENT_LOCKED = 14            # freeze the current orientation
ROTATION_270 = 3              # Surface.ROTATION_270
NORMAL_RES = (640, 480)


# ------------------------------------------------------- android helpers
def set_orientation(mode):
    if platform != 'android':
        return
    try:
        from jnius import autoclass
        from android.runnable import run_on_ui_thread

        @run_on_ui_thread
        def _apply():
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            activity.setRequestedOrientation(mode)

        _apply()
    except Exception as e:
        print('Orientation change failed:', e)


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
        return 2


class VolumeKeys:
    """Volume buttons change the image size. The music volume is parked at
    the middle; any change is read as a button press and then reset.
    The original volume is restored when the app is paused or closed."""
    STREAM = 3  # STREAM_MUSIC

    def __init__(self, on_step):
        self.on_step = on_step
        self.am = None
        self.orig = None
        self.mid = None
        self.ev = None

    def start(self):
        if platform != 'android' or self.ev is not None:
            return
        try:
            from jnius import autoclass, cast
            from android.runnable import run_on_ui_thread
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            context = autoclass('android.content.Context')
            self.am = cast('android.media.AudioManager',
                           activity.getSystemService(context.AUDIO_SERVICE))

            @run_on_ui_thread
            def _route():
                activity.setVolumeControlStream(self.STREAM)

            _route()
            maxv = self.am.getStreamMaxVolume(self.STREAM)
            if maxv < 2:
                return
            self.orig = self.am.getStreamVolume(self.STREAM)
            self.mid = maxv // 2
            self.am.setStreamVolume(self.STREAM, self.mid, 0)
            self.ev = Clock.schedule_interval(self._poll, 0.12)
        except Exception as e:
            print('Volume keys unavailable:', e)
            self.ev = None

    def _poll(self, dt):
        try:
            v = self.am.getStreamVolume(self.STREAM)
            if v != self.mid:
                self.on_step(1 if v > self.mid else -1)
                self.am.setStreamVolume(self.STREAM, self.mid, 0)
        except Exception as e:
            print('Volume poll failed:', e)

    def stop(self):
        if self.ev is not None:
            self.ev.cancel()
            self.ev = None
        try:
            if self.am is not None and self.orig is not None:
                self.am.setStreamVolume(self.STREAM, self.orig, 0)
        except Exception:
            pass


# ------------------------------------------------------------ UI helpers
def styled_button(text, **kw):
    kw.setdefault('font_size', sp(16))
    return Button(text=text, background_normal='', background_down='',
                  background_color=DARK_RED, color=TEXT, halign='center', **kw)


def styled_label(text, **kw):
    kw.setdefault('font_size', sp(15))
    return Label(text=text, color=TEXT, halign='center', **kw)


class VRSettingsPanel(BoxLayout):
    def __init__(self, vr, **kwargs):
        self.vr = vr
        super().__init__(orientation='vertical', padding=dp(14), spacing=dp(10),
                         size_hint=(0.86, 0.94),
                         pos_hint={'center_x': 0.5, 'center_y': 0.5}, **kwargs)

        with self.canvas.before:
            Color(*BLACK)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            Color(*DARK_RED)
            self._border = Line(rectangle=(*self.pos, *self.size), width=2)
        self.bind(pos=self._redraw, size=self._redraw)

        # header: title on the left, close button on the right
        header = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
        header.add_widget(styled_label('SETTINGS', bold=True, font_size=sp(22)))
        close_btn = styled_button('CLOSE', size_hint_x=None, width=dp(130))
        close_btn.bind(on_release=lambda *_: vr.close_settings())
        header.add_widget(close_btn)
        self.add_widget(header)

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(6),
                            bar_color=DARK_RED, scroll_type=['bars', 'content'])
        grid = GridLayout(cols=2, spacing=dp(10), padding=(0, 0, dp(8), 0),
                          size_hint_y=None, row_force_default=True,
                          row_default_height=dp(64))
        grid.bind(minimum_height=grid.setter('height'))
        scroll.add_widget(grid)
        self.add_widget(scroll)

        # 1. camera selector
        cam_row = BoxLayout(spacing=dp(6))
        prev_btn = styled_button('<', size_hint_x=None, width=dp(56))
        next_btn = styled_button('>', size_hint_x=None, width=dp(56))
        prev_btn.bind(on_release=lambda *_: vr.change_camera(-1))
        next_btn.bind(on_release=lambda *_: vr.change_camera(+1))
        self.cam_label = styled_label('')
        cam_row.add_widget(prev_btn)
        cam_row.add_widget(self.cam_label)
        cam_row.add_widget(next_btn)
        grid.add_widget(cam_row)

        # 2. status text
        self.status_label = styled_label('', font_size=sp(13))
        grid.add_widget(self.status_label)

        # 3. quality
        self.quality_btn = styled_button('')
        self.quality_btn.bind(on_release=self.toggle_quality)
        grid.add_widget(self.quality_btn)

        # 4. frame rate
        self.fps_btn = styled_button('')
        self.fps_btn.bind(on_release=self.toggle_fps)
        grid.add_widget(self.fps_btn)

        # 5. image size
        self.size_label = styled_label('', font_size=sp(14))
        self.size_slider = Slider(min=0.5, max=1.5, value=vr.size_scale,
                                  value_track=True, value_track_color=DARK_RED,
                                  cursor_size=(dp(28), dp(28)))
        self.size_slider.bind(value=self.change_size)
        cell = BoxLayout(orientation='vertical')
        cell.add_widget(self.size_label)
        cell.add_widget(self.size_slider)
        grid.add_widget(cell)

        # 6. gap
        self.gap_label = styled_label('', font_size=sp(14))
        self.gap_slider = Slider(min=0, max=400, value=vr.gap,
                                 value_track=True, value_track_color=DARK_RED,
                                 cursor_size=(dp(28), dp(28)))
        self.gap_slider.bind(value=self.change_gap)
        cell = BoxLayout(orientation='vertical')
        cell.add_widget(self.gap_label)
        cell.add_widget(self.gap_slider)
        grid.add_widget(cell)

        # 7. auto rotation
        self.rot_btn = styled_button('')
        self.rot_btn.bind(on_release=self.toggle_rotation)
        grid.add_widget(self.rot_btn)

        # 8. volume keys
        self.vol_btn = styled_button('')
        self.vol_btn.bind(on_release=self.toggle_volume)
        grid.add_widget(self.vol_btn)

        # 9. measured fps
        self.measure_label = styled_label('', font_size=sp(13))
        grid.add_widget(self.measure_label)

        # 10. version
        grid.add_widget(styled_label('Experimental Version', italic=True))

        self.refresh_labels()

    def _redraw(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        self._border.rectangle = (*self.pos, *self.size)

    def refresh_labels(self):
        vr = self.vr
        self.cam_label.text = 'Camera %d of %d' % (vr.cam_index + 1, vr.cam_count)
        self.status_label.text = vr.status
        res = '%dx%d' % vr.cur_res
        self.quality_btn.text = ('Quality: Maximum\n(%s)' % res if vr.quality == 'max'
                                 else 'Quality: Normal\n(%s)' % res)
        self.fps_btn.text = 'Frame rate: %s' % ('60 FPS' if vr.fps >= 60 else 'Normal (30 FPS)')
        self.size_label.text = 'Image size: %d%%' % round(vr.size_scale * 100)
        self.gap_label.text = 'Gap between images: %d px' % round(vr.gap)
        self.rot_btn.text = 'Auto rotation: %s' % ('ON' if vr.auto_rotate else 'OFF (locked)')
        self.vol_btn.text = 'Volume keys = size: %s' % ('ON' if vr.volume_keys else 'OFF')
        self.measure_label.text = 'Measured: camera %d fps / screen %d fps' % (
            round(vr.cam_fps), round(vr.disp_fps))

    def toggle_quality(self, *_):
        self.vr.set_quality('normal' if self.vr.quality == 'max' else 'max')

    def toggle_fps(self, *_):
        self.vr.set_fps(30 if self.vr.fps >= 60 else 60)
        self.refresh_labels()

    def toggle_rotation(self, *_):
        self.vr.set_auto_rotate(not self.vr.auto_rotate)
        self.refresh_labels()

    def toggle_volume(self, *_):
        self.vr.set_volume_keys(not self.vr.volume_keys)
        self.refresh_labels()

    def change_size(self, _inst, value):
        self.vr.size_scale = value
        self.refresh_labels()

    def change_gap(self, _inst, value):
        self.vr.gap = value
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
        self.target_index = 0
        self.cam_count = get_camera_count()
        self.size_scale = 1.0
        self.gap = 0.0
        self.fps = 30                 # 30 = normal, 60 = high
        self.quality = 'normal'       # 'normal' or 'max'
        self.auto_rotate = True
        self.volume_keys = True
        self.status = ''
        self.cur_res = NORMAL_RES
        self.rotation = 1
        self.camera = None
        self.panel = None
        self._frames = 0
        self.cam_fps = 0.0
        self.disp_fps = 0.0

        self.volume = VolumeKeys(self.adjust_size)

        # drawing instructions are created once and only updated per frame
        with self.canvas.before:
            Color(0, 0, 0, 1)
            self._bg = Rectangle(pos=(0, 0), size=(1, 1))
            Color(1, 1, 1, 1)
            self._cells = []
            for _ in range(2):
                scissor = ScissorPush(x=0, y=0, width=1, height=1)
                rect = Rectangle(pos=(0, 0), size=(0, 0))
                ScissorPop()
                self._cells.append((scissor, rect))

        # hidden Settings button (top-right corner)
        self.menu_btn = styled_button('Settings', size_hint=(None, None),
                                      size=(dp(150), dp(54)), font_size=sp(18),
                                      pos_hint={'right': 0.99, 'top': 0.97})
        self.menu_btn.opacity = 0
        self.menu_btn.disabled = True
        self.menu_btn.bind(on_release=lambda *_: self.open_settings())
        self.add_widget(self.menu_btn)
        self._hide_event = None

        # small message shown when the volume keys change the size
        self.toast = Label(text='', color=TEXT, font_size=sp(20), bold=True,
                           size_hint=(None, None), size=(dp(260), dp(40)),
                           pos_hint={'center_x': 0.5, 'y': 0.04})
        self.toast.opacity = 0
        self.add_widget(self.toast)

        self._tick = Clock.schedule_interval(self.update_vr, 1.0 / self.fps)
        Clock.schedule_interval(self._poll_rotation, 0.3)
        Clock.schedule_interval(self._measure, 1.0)

    # ---------------------------------------------------------- camera
    def start_camera(self, *_):
        if self.camera is None:
            self.restart_camera()

    def _release_camera(self):
        cam = self.camera
        if cam is None:
            return
        try:
            core = cam._camera
            cam.play = False
            Clock.unschedule(core._update)
            core._android_camera.release()   # frees the hardware for the next camera
        except Exception as e:
            print('Camera release:', e)
        try:
            self.remove_widget(cam)
        except Exception:
            pass
        self.camera = None

    def _try_open(self, index, res):
        try:
            cam = Camera(index=index, resolution=res, play=True,
                         size_hint=(None, None), size=(1, 1))
            cam.opacity = 0
            self.add_widget(cam)
            self.camera = cam
            self.cur_res = res
            try:
                cam._camera.bind(on_texture=self._count_frame)
            except Exception:
                pass
            return True
        except Exception as e:
            print('Camera %d open failed: %s' % (index, e))
            self.camera = None
            return False

    def _read_sizes(self):
        try:
            flat = str(self.camera._camera._android_camera.getParameters().flatten())
            for part in flat.split(';'):
                if part.startswith('preview-size-values='):
                    out = []
                    for p in part.split('=', 1)[1].split(','):
                        w, h = p.split('x')
                        out.append((int(w), int(h)))
                    return out
        except Exception as e:
            print('Could not read sizes:', e)
        return []

    def restart_camera(self):
        index = self.target_index
        previous = self.cam_index
        self._release_camera()
        self._frames = 0

        ok = self._try_open(index, NORMAL_RES)
        if ok and self.quality == 'max':
            sizes = [s for s in self._read_sizes() if s[0] <= 1920 and s[1] <= 1080]
            best = max(sizes, key=lambda s: s[0] * s[1]) if sizes else None
            if best and best != NORMAL_RES:
                self._release_camera()
                if not self._try_open(index, best):
                    ok = self._try_open(index, NORMAL_RES)

        if ok:
            self.cam_index = index
            self.status = 'Camera %d is active' % (index + 1)
        else:
            self.status = 'Camera %d is not available' % (index + 1)
            self.cam_index = previous
            self._try_open(previous, NORMAL_RES)

        Clock.schedule_once(self.apply_camera_fps, 0.8)
        self.refresh_panel()

    def change_camera(self, step):
        self.target_index = (self.target_index + step) % self.cam_count
        self.restart_camera()

    def set_quality(self, quality):
        self.quality = quality
        self.restart_camera()

    def set_fps(self, fps):
        self.fps = fps
        self._tick.cancel()
        self._tick = Clock.schedule_interval(self.update_vr, 1.0 / fps)
        self.apply_camera_fps()

    def apply_camera_fps(self, *_):
        """Make the camera itself deliver 30 or 60 frames per second.
        Kivy refreshes the camera image on a 30 fps timer by default, so that
        timer is changed too. Whether the phone's camera really reaches 60 at
        the chosen quality is shown in the 'Measured' line in Settings."""
        if self.camera is None:
            return
        try:
            core = self.camera._camera
            core.fps = float(self.fps)
            if not core.stopped:
                Clock.unschedule(core._update)
                Clock.schedule_interval(core._update, 1.0 / self.fps)
        except Exception as e:
            print('Camera timer change failed:', e)
        if platform != 'android':
            return
        try:
            cam = self.camera._camera._android_camera
            params = cam.getParameters()
            ranges = []
            for part in str(params.flatten()).split(';'):
                if part.startswith('preview-fps-range-values='):
                    for pair in part.split('=', 1)[1].strip('()').split('),('):
                        lo, hi = pair.split(',')
                        ranges.append((int(lo), int(hi)))
            if self.fps >= 60:
                cands = [r for r in ranges if r[1] >= 60000]
            else:
                cands = [r for r in ranges if r[1] <= 30000]
            if not cands:
                return
            best = max(cands, key=lambda r: (r[1], r[0]))
            cam.stopPreview()
            params.setPreviewFpsRange(best[0], best[1])
            cam.setParameters(params)
            cam.startPreview()
        except Exception as e:
            print('Camera fps range change failed:', e)

    def _count_frame(self, *_):
        self._frames += 1

    def _measure(self, dt):
        self.cam_fps = self._frames / dt
        self._frames = 0
        self.disp_fps = Clock.get_fps()
        if self.panel is not None:
            self.panel.refresh_labels()

    def refresh_panel(self):
        if self.panel is not None:
            self.panel.refresh_labels()

    # ------------------------------------------------- rotation & volume
    def _poll_rotation(self, dt):
        self.rotation = get_display_rotation()

    def set_auto_rotate(self, value):
        self.auto_rotate = value
        set_orientation(ORIENT_SENSOR_LANDSCAPE if value else ORIENT_LOCKED)

    def set_volume_keys(self, value):
        self.volume_keys = value
        if value:
            self.volume.start()
        else:
            self.volume.stop()

    def adjust_size(self, step):
        self.size_scale = min(1.5, max(0.5, round(self.size_scale + step * 0.05, 2)))
        self.show_toast('Image size: %d%%' % round(self.size_scale * 100))
        if self.panel is not None:
            self.panel.size_slider.value = self.size_scale

    def show_toast(self, text):
        self.toast.text = text
        Animation.cancel_all(self.toast, 'opacity')
        self.toast.opacity = 1
        (Animation(duration=0.8) + Animation(opacity=0, duration=0.4)).start(self.toast)

    # ------------------------------------------- hidden Settings button
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

    def open_settings(self):
        if self.panel is not None:
            return
        if self._hide_event:
            self._hide_event.cancel()
        self.menu_btn.opacity = 0
        self.menu_btn.disabled = True
        self.panel = VRSettingsPanel(self)
        self.add_widget(self.panel)

    def close_settings(self):
        if self.panel is not None:
            self.remove_widget(self.panel)
            self.panel = None

    # ---------------------------------------------------------- drawing
    def update_vr(self, dt):
        w, h = Window.size
        self._bg.size = (w, h)
        tex = self.camera.texture if self.camera is not None else None
        if not tex:
            for _scissor, rect in self._cells:
                rect.size = (0, 0)
            return

        half_w = w / 2.0
        cell_w = half_w - self.gap / 2.0

        # In the "other" landscape direction the camera image has to be
        # turned 180 degrees so it always stays upright.
        tc = list(tex.tex_coords)
        if self.rotation == ROTATION_270:
            tc = tc[4:] + tc[:4]

        tw, th = tex.size
        fit = min(cell_w / float(tw), h / float(th)) * self.size_scale
        iw, ih = tw * fit, th * fit

        for cell_x, (scissor, rect) in zip((0, half_w + self.gap / 2.0), self._cells):
            scissor.x, scissor.y = int(cell_x), 0
            scissor.width, scissor.height = int(cell_w), int(h)
            rect.texture = tex
            rect.tex_coords = tc
            rect.pos = (cell_x + (cell_w - iw) / 2.0, (h - ih) / 2.0)
            rect.size = (iw, ih)


class VRApp(App):
    def build(self):
        self.vr = VRWidget()
        return self.vr

    def on_start(self):
        set_orientation(ORIENT_SENSOR_LANDSCAPE)
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission

                def _done(permissions, results):
                    Clock.schedule_once(self._begin)

                request_permissions([Permission.CAMERA], _done)
                return
            except Exception as e:
                # Pydroid 3 does not support this API; grant the camera
                # permission to Pydroid in the phone's app settings.
                print('Permission request unavailable:', e)
        Clock.schedule_once(self._begin, 0.5)

    def _begin(self, *_):
        self.vr.start_camera()
        if self.vr.volume_keys:
            self.vr.volume.start()

    def on_pause(self):
        self.vr.volume.stop()
        return True

    def on_resume(self):
        if self.vr.volume_keys:
            self.vr.volume.start()

    def on_stop(self):
        self.vr.volume.stop()


if __name__ == '__main__':
    VRApp().run()
