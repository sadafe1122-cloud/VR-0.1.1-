[app]
title = VR Camera
package.name = vrcamera
package.domain = org.vrcamera
source.dir = .
source.include_exts = py
version = 0.1
requirements = python3,kivy==2.3.1,pyjnius,android
orientation = landscape
fullscreen = 1
android.permissions = CAMERA
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
