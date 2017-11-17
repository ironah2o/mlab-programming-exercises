#!/usr/bin/env python3

import math
import re

import numpy as np
import pyaudio


class MusicPart(object):

    RATE = 44100
    BASE_KEY_FACTOR = {
        "C": -9,
        "D": -7,
        "E": -5,
        "F": -4,
        "G": -2,
        "A": 0,
        "B": 2,
    }

    def __init__(self, bpm=60, volume=0.1):
        self.bpm = bpm
        self.wave = np.empty(0)
        self.key_factor = self.__class__.BASE_KEY_FACTOR.copy()
        self.volume = volume

    def rest(self, length=1):
        zero_wave = np.zeros(
            int(length * (60 / self.bpm) * self.__class__.RATE))
        self.wave = np.concatenate((self.wave, zero_wave))

    def append_tone(self, scales, length=1, backward=False):
        waves = []

        scale_list = self._normalize_scale_argument(scales)
        for scale in scale_list:
            freq = self._freq_from_scale(scale)

            single_wave = self._generate_single_wave(freq, length)
            waves.append(single_wave)

        new_wave = np.sum(waves, axis=0) * self.volume
        if backward:
            back_length = len(new_wave)
            self.wave[-back_length:] += new_wave
        else:
            self.wave = np.concatenate((self.wave, new_wave))

    def _generate_single_wave(self, freq, length=1):
        step = (2 * math.pi) * freq / self.__class__.RATE  # 2πf*(1/rate)
        single_wave = np.sin(step * np.arange(
            int(length * (60 / self.bpm) * self.__class__.RATE)))  # sin(2πft)
        return single_wave

    def _normalize_scale_argument(self, scale):
        if isinstance(scale, str):
            return [scale]
        else:
            return scale

    def _freq_from_scale(self, scale):
        match = re.match(r"([a-gA-G])([b#]?)([0-9]+)$", scale)
        if match is None:
            raise Exception
        key, accidental, octave_str = match.groups()

        factor = self.key_factor[key.upper()]
        octave = int(octave_str)

        if accidental == "#":
            factor += 1
        elif accidental == "b":
            factor -= 1

        freq = 440 * (2**((octave - 4) + factor / 12))
        return freq

    def play(self):
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paFloat32, channels=1,
                         rate=self.__class__.RATE, output=True)
        out_wave = self.wave
        stream.write(out_wave.astype(np.float32).tostring())

    def change_key(self, scales, signature):
        factor = 0
        if signature == "#":
            factor = 1
        elif signature == "b":
            factor = -1

        scale_list = self._normalize_scale_argument(scales)
        self.key_factor = self.__class__.BASE_KEY_FACTOR.copy()

        for scale in scale_list:
            self.key_factor[scale] += factor


class Music(object):

    def __init__(self, main_volume=1):
        self.parts = []
        self.main_volume = main_volume

    def add_part(self, part):
        self.parts.append(part)

    def _marged_wave(self):
        wave = np.empty(1)
        for part in self.parts:
            wave = self._marge(wave, part.wave)
        return wave

    def _marge(self, wave1, wave2):
        if len(wave1) < len(wave2):
            long_wave = wave2.copy()
            short_wave = wave1
        else:
            long_wave = wave1.copy()
            short_wave = wave2
        long_wave[:len(short_wave)] += short_wave
        return long_wave

    def play(self):
        out_wave = self._marged_wave() * self.main_volume

        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paFloat32, channels=1,
                         rate=MusicPart.RATE, output=True)
        stream.write(out_wave.astype(np.float32).tostring())


def amazing_grace():
    bpm = 60

    music = MusicPart(bpm=bpm)
    music.change_key("F", "#")

    music.append_tone(["d4", "b3"])
    music.append_tone(["g4", "b3"], 2)
    music.append_tone("b4", 0.5)
    music.append_tone("g4", 0.5)
    music.append_tone("d4", backward=True)
    music.append_tone(["b4", "d4"], 2)
    music.append_tone(["a4", "c4"])
    music.append_tone(["g4", "b3"], 2)
    music.append_tone(["e4", "c4"])
    music.append_tone(["d4", "b3"], 2)
    music.rest()

    return music


def canon():
    bpm = 90

    treble = MusicPart(bpm=bpm)
    treble.change_key(["C", "F"], "#")

    bass = MusicPart(bpm=bpm)
    bass.change_key(["A", "E"], "#")

    # treble part
    treble.append_tone(["f4", "d4"], 2)
    treble.append_tone(["e4", "c4"], 2)
    treble.append_tone(["d4", "b3"], 2)
    treble.append_tone(["c4", "a3"], 2)

    treble.append_tone(["b3", "g3"], 2)
    treble.append_tone(["a3", "f3"], 2)
    treble.append_tone(["b3", "g3"], 2)
    treble.append_tone(["c4", "a3"], 2)

    treble.append_tone(["d5", "f4"], 2)
    treble.append_tone(["c5", "a4"], 2)
    treble.append_tone(["b4", "d4"], 2)
    treble.append_tone(["a4", "f4"], 2)

    treble.append_tone(["g4", "b3"], 2)
    treble.append_tone(["f4", "d4"], 2)
    treble.append_tone(["g4", "b3"], 2)
    treble.append_tone(["a4", "c4"], 2)

    # bass part
    bass.append_tone("d3", 2)
    bass.append_tone("a2", 2)
    bass.append_tone("b2", 2)
    bass.append_tone("f3", 2)
    bass.append_tone("g3", 2)
    bass.append_tone("d3", 2)
    bass.append_tone("g3", 2)
    bass.append_tone("f3", 2)

    bass.append_tone("d3")
    bass.append_tone("f3")
    bass.append_tone("a3")
    bass.append_tone("g3")
    bass.append_tone("f3")
    bass.append_tone("d3")
    bass.append_tone("f3")
    bass.append_tone("e3")

    bass.append_tone("d3")
    bass.append_tone("b2")
    bass.append_tone("d3")
    bass.append_tone("a2")
    bass.append_tone("g2")
    bass.append_tone("b2")
    bass.append_tone("c3")
    bass.append_tone("a2")
    bass.rest()

    music = Music()
    music.add_part(treble)
    music.add_part(bass)

    return music


def jupiter():
    bpm = 90

    music = MusicPart(bpm=bpm)
    music.change_key(["A", "B", "E"], "b")

    music.append_tone("g3", .5)
    music.append_tone("b3", .5)

    music.append_tone(["c4", "a3"])
    music.append_tone("c4", .5)
    music.append_tone("e4", .5)
    music.append_tone(["d4", "a3"], .75)
    music.append_tone("b3", .25)

    music.append_tone(["e4", "b3"], .5)
    music.append_tone("f4", .5)
    music.append_tone("e4")
    music.append_tone(["d4", "b3"])

    music.append_tone(["c4", "a3"], .5)
    music.append_tone("d4", .5)
    music.append_tone("c4")
    music.append_tone(["b3", "f3"])

    music.append_tone(["g3", "e3"], 2)
    music.rest()

    return music


def main():
    amazing_grace().play()
    jupiter().play()
    canon().play()


if __name__ == '__main__':
    main()
