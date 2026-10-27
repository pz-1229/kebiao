[app]

title = 简课
package.name = jianke
package.domain = com.jianke

source.dir = .
source.include_exts = py,png,jpg,atlas,ttf,otf,txt,json,md
source.include_patterns = assets/*,jianke_app/*
source.exclude_dirs = tests,tools,previews,docs,scripts,.github,.ui-test-data,.preview-data,__pycache__,bin,.mypy_cache
source.exclude_patterns = *.pyc,*.pyo,.DS_Store

version = 1.0.0
requirements = python3,kivy==2.3.1

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/assets/images/icon.png
presplash.filename = %(source.dir)s/assets/images/presplash.png
android.presplash_color = #F4F2EC

# 只打包 arm64，构建更快；2019 年后的手机基本都是 arm64。
android.archs = arm64-v8a
android.api = 33
android.minapi = 23
android.ndk = 25b
android.ndk_api = 23
android.accept_sdk_license = True
android.private_storage = True
android.release_artifact = apk
android.logcat_filters = *:S python:D

# 不申请联网权限：课程表完全离线。
android.permissions =

[buildozer]
log_level = 2
warn_on_root = 1
