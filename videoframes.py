# -*- coding: utf-8 -*-

import platform
import sys
import time

from PyQt5 import QtWidgets, QtCore, uic
from containers import LiveStreamContainer, RewindedStreamContainer
from constants import *

class _VideoFrame(QtWidgets.QFrame):
    """An class representing a QFrame object containing a libVLC media player.

    Args:
        vlc_instance: VLC instance object.
    """
    def __init__(self, vlc_instance):
        super(_VideoFrame, self).__init__()
        self.player = vlc_instance.media_player_new()

        # Build the ui for this videoFrame
        self.setup_ui()

        self.is_muted = False

    def setup_ui(self):
        uic.loadUi("ui/frame.ui", self)
        # Find the draw area
        self.draw_area = self.findChild(QtCore.QObject, "drawArea")
        # Connect the playback toggle to the toolbox
        # TODO: Some other solution
        self.findChild(QtCore.QObject, "toolButton").clicked.connect(self.toggle_playback)

        # Bind the player
        if platform.system() == "Linux":
            self.player.set_xwindow(self.draw_area.winId())
        elif platform.system() == "Windows":
            self.player.set_hwnd(self.draw_area.winId())
        else:
            sys.exit("Platform unsupported.")

    def setup_actions(self):
        """Sets up the actions in the context menu provided."""
        self.mute_action = self.context_menu.addAction("Mute stream")
        self.mute_action.setCheckable(True)

        if self.player.audio_get_mute():
            self.mute_action.setChecked(True)
        else:
            self.mute_action.setChecked(False)

        self.context_menu.addSeparator()

    def check_actions(self, event):
        """Checks if the user action matches any of the actions."""
        user_action = self.context_menu.exec_(self.mapToGlobal(event.pos()))

        if user_action == self.mute_action:
            if self.player.audio_get_mute():
                self.player.audio_set_mute(False)
                self.is_muted = False
            else:
                self.player.audio_set_mute(True)
                self.is_muted = True

        return user_action

    def context_menu(self, event):
        """Opens a menu upon right clicking the frame."""
        self.context_menu = QtWidgets.QMenu(parent=self)

    def toggle_playback(self, event):
        """Toggles playback of a stream. How the playback itself is done is
        handeled by the deriving class.
        """
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

class LiveVideoFrame(_VideoFrame):
    """A class representing a VideoFrame containing a **live** stream.

    Args:
        vlc_instance: VLC instance object.
        stream_info: Dictionary containing the URL ('url') as well as the
            quality ('quality') of the requested stream.
    """
    def __init__(self, vlc_instance, stream_info):
        super(LiveVideoFrame, self).__init__(vlc_instance)
        self.vlc_instance = vlc_instance
        self.stream = LiveStreamContainer(vlc_instance, stream_info)
        self.player.set_media(self.stream.media)
        self.player.play()

        # Setup attribute used for the rewinded stream
        self.rewinded = None

    def setup_ui(self):
        super(LiveVideoFrame, self).setup_ui()

        # Hide the slider
        # TODO: Perhaps it should not even be created?
        # is there a huge overhead for QtWidgets?
        self.findChild(QtCore.QObject, "seek_slider").hide()
        # Connect the rewind button
        self.findChild(QtCore.QObject, "rewind_button").clicked.connect(self.rewind)

    def setup_actions(self):
        super(LiveVideoFrame, self).setup_actions()
        quality_submenu = QtWidgets.QMenu("Change quality", parent=self)

        # Add the quality options to the submenu.
        self.quality_actions = []
        for opt in self.stream.filtered_qualities:
            action = quality_submenu.addAction(opt)
            action.setCheckable(True)

            if opt == self.stream.quality:
                action.setChecked(True)
            else:
                action.setChecked(False)

            self.quality_actions.append(action)

        self.context_menu.addMenu(quality_submenu)

    def check_actions(self, event):
        user_action = super(LiveVideoFrame, self).check_actions(event)

        for quality_action in self.quality_actions:
            quality = quality_action.text()
            if user_action == quality_action and quality != self.stream.quality:
                self.change_stream_quality(quality)

    def contextMenuEvent(self, event):
        super(LiveVideoFrame, self).context_menu(event)
        self.setup_actions()

        user_action = self.check_actions(event)

    def change_stream_quality(self, quality):
        self.player.stop()
        self.stream.change_stream_quality(quality)
        self.player.play()

    def rewind(self):
        if self.rewinded is None:
            self.rewinded = RewindedVideoFrame(self.vlc_instance, self.stream.buffer, self)
            self.rewinded.show()

class RewindedVideoFrame(_VideoFrame):
    """A class representing a VideoFrame containing a **rewinded** stream.

    Args:
        vlc_instance: VLC instance object.
        stream_buffer: A reference to the buffer that should be copied and
            played from.
    """
    def __init__(self, vlc_instance, stream_buffer, parent):
        super(RewindedVideoFrame, self).__init__(vlc_instance)
        # Set the parent
        self.parent = parent

        self.stream = RewindedStreamContainer(vlc_instance, stream_buffer)
        self.stream.on_seek = self.on_seek
        self.player.set_media(self.stream.media)
        self.player.play()

    def setup_ui(self):
        super(RewindedVideoFrame, self).setup_ui()
        # Find the slider
        self.slider = self.findChild(QtCore.QObject, "seek_slider")
        # Seek when the slider is released
        self.slider.pressed = False
        self.slider.sliderReleased.connect(self.scrub)
        self.slider.sliderPressed.connect(self.slider_pressed)
        # Hide the rewind button:
        self.findChild(QtCore.QObject, "rewind_button").hide()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_slider_value)
        self.timer.start(1)

    def closeEvent(self, event):
        """Called whenever the window is closed
        """
        # First stop and release the media player
        self.player.stop()
        self.player.release()
        # Stop the timer
        self.timer.stop()
        # To remove the rewinded video window;
        # Let the garbage collector do its magic
        self.parent.rewinded = None

    def on_seek(self, offset):
        """Called when the underlying media_player is trying to seek
        """
        self.slider.pressed = False

    def contextMenuEvent(self, event):
        super(RewindedVideoFrame, self).context_menu(event)
        self.setup_actions()
        user_action = self.check_actions(event)

    def slider_pressed(self):
        """Called whenever the slider is pressed
        Consequently stops the slider value from getting updated
        """
        self.slider.pressed = True

    def scrub(self):
        """Called whenever the slider is released, which is followed by a scrub
        """
        self.player.set_position(self.slider.value()/SLIDER_MAX_VALUE)

    def update_slider_value(self):
        """Updates the slider with a guesstimate of video position
        """
        # Some guessing magic to get the timing right, kind of works for 480p30
        percentage_played = self.player.get_time()/(145*len(self.stream.buffer))
        if not self.slider.pressed:
            self.slider.setValue(percentage_played*SLIDER_MAX_VALUE)
