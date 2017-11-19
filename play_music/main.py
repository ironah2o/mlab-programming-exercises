#!/usr/bin/env python3

import math
import re

import numpy as np
import pyaudio


class MusicPart(object):
    """五線譜のパート1つ分を表すクラス"""

    RATE = 44100  # sample rate
    BASE_KEY_FACTOR = {  # ラの音を基準にしたときの半音の隔たり
        'C': -9,
        'D': -7,
        'E': -5,
        'F': -4,
        'G': -2,
        'A': 0,
        'B': 2,
    }

    def __init__(self, bpm=60, volume=0.1):
        self._wave = np.empty(0)

        self.bpm = bpm
        self.key_factor = self.__class__.BASE_KEY_FACTOR.copy()
        self.volume = volume

    # Private methods

    def _generate_single_wave(self, freq, length=1):
        step = (2 * math.pi) * freq / self.__class__.RATE  # 2πf*(1/rate)
        single_wave = np.sin(step * np.arange(
            int(length * (60 / self.bpm) * self.__class__.RATE)))  # sin(2πft)
        return single_wave

    def _normalize_scale_argument(self, scales):
        """リストでない単一のscale入力をリスト化する．リストならそのまま

        例： "d#3" -> ["d#3"], ["c2"] -> ["c2"]
        """
        if isinstance(scales, str):
            return [scales]
        else:
            return scales

    def _freq_from_scale(self, scale):
        """単一のscaleに対する周波数を返す

        例： "c#5" -> 554.365, "a5"-> 880.000
        """

        # 正規表現で音階，変化記号，オクターブ番号を抽出
        match = re.match(r'([a-gA-G])([b#]?)([0-9]+)$', scale)
        if match is None:
            raise Exception
        key, accidental, octave_str = match.groups()

        factor = self.key_factor[key.upper()]
        octave = int(octave_str)

        if accidental == '#':
            factor += 1
        elif accidental == 'b':
            factor -= 1

        freq = 440 * (2**((octave - 4) + factor / 12))
        return freq

    # Public methods
    def rest(self, length=1):
        """休符

        length: 休符の長さ．4分休符が1
        """
        zero_wave = np.zeros(
            int(length * (60 / self.bpm) * self.__class__.RATE))
        self._wave = np.concatenate((self._wave, zero_wave))

    def append_tone(self, scales, length=1, backward=False):
        """音符を追加する

        cale: 音符を表す文字列，またはそのリスト．音階の大文字小文字は区別しない
        例: ドの音を鳴らす場合 "c4"
        高いド#の音を鳴らす場合 "C#5"
        ドとミbの音を鳴らす場合 ["c4","Eb4"]
        length: 音の長さ．4分音符が1
        backward=Falseの時，前の音符に続いて音符を鳴らす
        backward=Tryeの時，length分前から，前の音符にかぶせて音符をならす
        """

        waves = []

        scale_list = self._normalize_scale_argument(scales)
        for scale in scale_list: # 音階ごとのsin波を順にwavesに追加する
            freq = self._freq_from_scale(scale)
            single_wave = self._generate_single_wave(freq, length)
            waves.append(single_wave)

        new_wave = np.sum(waves, axis=0)  # 音の波形をすべて足す
        if backward:
            back_length = len(new_wave)
            self._wave[-back_length:] += new_wave
        else:
            self._wave = np.concatenate((self._wave, new_wave))

    def play(self):
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paFloat32, channels=1,
                         rate=self.__class__.RATE, output=True)
        out_wave = self.get_wave()
        stream.write(out_wave.astype(np.float32).tostring())

    def change_key(self, scales, signature):
        """調を変更する

        例:
        変ホ長調：change_key(['A', 'B', 'E'], 'b')
        ト長調  ：change_key('F', '#')
        """
        factor = 0
        if signature == '#':
            factor = 1
        elif signature == 'b':
            factor = -1

        scale_list = self._normalize_scale_argument(scales)
        self.key_factor = self.__class__.BASE_KEY_FACTOR.copy()  # 一度調をリセット

        for scale in scale_list:
            self.key_factor[scale] += factor

    # getter
    def get_wave(self):
        return self._wave() * self.volume


class Music(object):
    """MusicPartをまとめるクラス

    MusicPartで作ったパートごとの音を同時に鳴らす
    add_part(part)でパートを追加したあとで，play()で鳴らせる
    """

    def __init__(self, main_volume=1):
        self.parts = []
        self.main_volume = main_volume

    # Private methods
    def _marged_wave(self):
        """Partごとの音を合成した波形を返す"""

        wave = np.empty(1)
        for part in self.parts:
            wave = self._marge(wave, part.get_wave())
        return wave

    def _marge(self, wave1, wave2):
        """2つの波形を合成する"""

        if len(wave1) < len(wave2):
            long_wave = wave2.copy()
            short_wave = wave1
        else:
            long_wave = wave1.copy()
            short_wave = wave2
        long_wave[:len(short_wave)] += short_wave
        return long_wave

    # Public methods
    def add_part(self, part):
        self.parts.append(part)

    def play(self):
        out_wave = self._marged_wave() * self.main_volume

        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paFloat32, channels=1,
                         rate=MusicPart.RATE, output=True)
        stream.write(out_wave.astype(np.float32).tostring())


def amazing_grace():
    """Amazing GraceのMusicインスタンスを作成する関数"""

    bpm = 60

    music = MusicPart(bpm=bpm)
    music.change_key('F', '#')

    music.append_tone(['d4', 'b3'])
    music.append_tone(['g4', 'b3'], 2)
    music.append_tone('b4', 0.5)
    music.append_tone('g4', 0.5)
    music.append_tone('d4', backward=True)
    music.append_tone(['b4', 'd4'], 2)
    music.append_tone(['a4', 'c4'])
    music.append_tone(['g4', 'b3'], 2)
    music.append_tone(['e4', 'c4'])
    music.append_tone(['d4', 'b3'], 2)
    music.rest()

    return music


def canon():
    """パッヘルベルのカノンのMusicインスタンスを作成する関数"""

    bpm = 90

    treble = MusicPart(bpm=bpm)
    treble.change_key(['C', 'F'], '#')

    bass = MusicPart(bpm=bpm)
    bass.change_key(['A', 'E'], '#')

    # treble part
    treble.append_tone(['f4', 'd4'], 2)
    treble.append_tone(['e4', 'c4'], 2)
    treble.append_tone(['d4', 'b3'], 2)
    treble.append_tone(['c4', 'a3'], 2)

    treble.append_tone(['b3', 'g3'], 2)
    treble.append_tone(['a3', 'f3'], 2)
    treble.append_tone(['b3', 'g3'], 2)
    treble.append_tone(['c4', 'a3'], 2)

    treble.append_tone(['d5', 'f4'], 2)
    treble.append_tone(['c5', 'a4'], 2)
    treble.append_tone(['b4', 'd4'], 2)
    treble.append_tone(['a4', 'f4'], 2)

    treble.append_tone(['g4', 'b3'], 2)
    treble.append_tone(['f4', 'd4'], 2)
    treble.append_tone(['g4', 'b3'], 2)
    treble.append_tone(['a4', 'c4'], 2)

    # bass part
    bass.append_tone('d3', 2)
    bass.append_tone('a2', 2)
    bass.append_tone('b2', 2)
    bass.append_tone('f3', 2)
    bass.append_tone('g3', 2)
    bass.append_tone('d3', 2)
    bass.append_tone('g3', 2)
    bass.append_tone('f3', 2)

    bass.append_tone('d3')
    bass.append_tone('f3')
    bass.append_tone('a3')
    bass.append_tone('g3')
    bass.append_tone('f3')
    bass.append_tone('d3')
    bass.append_tone('f3')
    bass.append_tone('e3')

    bass.append_tone('d3')
    bass.append_tone('b2')
    bass.append_tone('d3')
    bass.append_tone('a2')
    bass.append_tone('g2')
    bass.append_tone('b2')
    bass.append_tone('c3')
    bass.append_tone('a2')
    bass.rest()

    music = Music()
    music.add_part(treble)
    music.add_part(bass)

    return music


def jupiter():
    """JupiterのMusicインスタンスを作成する関数"""

    bpm = 90

    music = MusicPart(bpm=bpm)
    music.change_key(['A', 'B', 'E'], 'b')

    music.append_tone('g3', .5)
    music.append_tone('b3', .5)

    music.append_tone(['c4', 'a3'])
    music.append_tone('c4', .5)
    music.append_tone('e4', .5)
    music.append_tone(['d4', 'a3'], .75)
    music.append_tone('b3', .25)

    music.append_tone(['e4', 'b3'], .5)
    music.append_tone('f4', .5)
    music.append_tone('e4')
    music.append_tone(['d4', 'b3'])

    music.append_tone(['c4', 'a3'], .5)
    music.append_tone('d4', .5)
    music.append_tone('c4')
    music.append_tone(['b3', 'f3'])

    music.append_tone(['g3', 'e3'], 2)
    music.rest()

    return music


def main():
    amazing_grace().play()
    jupiter().play()
    canon().play()


if __name__ == '__main__':
    main()
