#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Example application for the Abios Gaming - Desktop Stream Viewer.
# Sven Anderzén - 2017

# GTK imports.
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import GObject, Gio, Gtk, GdkX11

import sys
import ctypes

import vlc
import streamlink
import callbacks as cb

class Application(Gtk.Application):
    
    def __init__(self, application_id, flags, stream_info):
        Gtk.Application.__init__(self, application_id = application_id, flags = flags)
        self.connect("activate", self.activate)

        # Kick up a VLC instance. 
        self.vlc_instance = vlc.Instance("--no-xlib")
        
        # Streamlink streams.
        #self.stream_one = self.get_stream(stream_info[0])
        #self.stream_two = self.get_stream(stream_info[1])
        streams = streamlink.streams(stream_info[0]["url"])
        self.stream_one = streams[stream_info[0]["quality"]].open()
        streams = streamlink.streams(stream_info[1]["url"])
        self.stream_two = streams[stream_info[1]["quality"]].open()

        # Create media callbacks.
        #self.media_one = self.create_media_callbacks(self.stream_one)
        #self.media_two = self.create_media_callbacks(self.stream_two)
        opaque_one = ctypes.cast(ctypes.pointer(ctypes.py_object(self.stream_one)), ctypes.c_void_p) 
        self.media_one = self.vlc_instance.media_new_callbacks(
            cb.callbacks["read"],
            cb.callbacks["open"],
            cb.callbacks["seek"],
            cb.callbacks["close"],
            opaque_one
        )
        opaque_two = ctypes.cast(ctypes.pointer(ctypes.py_object(self.stream_one)), ctypes.c_void_p) 
        self.media_two = self.vlc_instance.media_new_callbacks(
            cb.callbacks["read"],
            cb.callbacks["open"],
            cb.callbacks["seek"],
            cb.callbacks["close"],
            opaque_two
        )

    def activate(self, *args):
        ApplicationWindow(self)

    def get_stream(self, stream_info):
        streams = streamlink.streams(stream_info["url"])
        stream = streams[stream_info["quality"]].open()
        
        return stream

    def create_media_callbacks(self, stream):
        opaque = ctypes.cast(ctypes.pointer(ctypes.py_object(stream)), ctypes.c_void_p) 
        media = self.vlc_instance.media_new_callbacks(
            cb.callbacks["read"],
            cb.callbacks["open"],
            cb.callbacks["seek"],
            cb.callbacks["close"],
            opaque
        )

        return media

class ApplicationWindow(object):
    
    def __init__(self, application):
        self.application = application

        # Load Glade UI file.
        try:
            builder = Gtk.Builder.new_from_file("gui.glade")
            builder.connect_signals(self)
        except GObject.GError:
            print("Could not read gui.glade.")
            raise

        self.window = builder.get_object("window")
        self.window.set_application(application)

        self.window.set_size_request(1280, 720)
        self.window.show()

    def onDrawReadyOne(self, widget,  *args):
        player = self.application.vlc_instance.media_player_new()
        xid = widget.get_window().get_xid()
        player.set_xwindow(xid)
        player.set_media(self.application.media_one)
        player.play()

    # Temporary workaround since we read stream_info from CLI and not GUI atm.
    def onDrawReadyTwo(self, widget,  *args):
        player = self.application.vlc_instance.media_player_new()
        xid = widget.get_window().get_xid()
        player.set_xwindow(xid)
        player.set_media(self.application.media_two)
        player.play()

    def onDelete(self, *args):
        self.application.vlc_instance.release()
        self.window.destroy()

def main():

    try:
        stream_info = [{}, {}]
        stream_info[0]["url"], stream_info[0]["quality"] = sys.argv[1], sys.argv[2]
        stream_info[1]["url"], stream_info[1]["quality"] = sys.argv[3], sys.argv[4]
    except Exception as e:
        sys.exit("Usage: {} <url> <quality> <url> <quality>".format(__file__))

    app = Application("com.abiosgaming", Gio.ApplicationFlags.FLAGS_NONE, stream_info)
    app.run()

if __name__ == "__main__":
    main()