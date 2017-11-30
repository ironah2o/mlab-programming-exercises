#!/usr/bin/env python3

import functools
import math
import re
import scipy.stats

import numpy as np
import pyaudio


def merge_wave(wave1, wave2):
    """長さの異なる2つのndarrayを合成する"""

    if len(wave1) > len(wave2):
        long_wave, short_wave = wave1, wave2
    else:
        long_wave, short_wave = wave2, wave1

    new_wave = long_wave.copy()
    new_wave[:len(short_wave)] += short_wave
    return new_wave


def normalize_scale_argument(scales):
    """リストでない単一のscale入力をリスト化する．リストならそのまま

    例： "d#3" -> ["d#3"], ["c2"] -> ["c2"]
    """
    if isinstance(scales, str):
        return [scales]
    else:
        return scales


class KeyConfig(dict):
    """長調，単調などの調の変更を管理するクラス

    """

    BASE_KEY_FACTOR = {  # ラの音を基準にしたときの半音の隔たり
        'C': -9,
        'D': -7,
        'E': -5,
        'F': -4,
        'G': -2,
        'A': 0,
        'B': 2,
    }

    BASE_KEY_CHANGE = {  # 変更値のデフォルト
        'C': 0,
        'D': 0,
        'E': 0,
        'F': 0,
        'G': 0,
        'A': 0,
        'B': 0,
    }

    def __init__(self, scales=None, signature=None):
        """イニシャライザ

        scalesとsignatureを両方入力した場合はchange_key()が呼ばれる
        """
        super().__init__()
        self.update(self.__class__.BASE_KEY_CHANGE)
        if scales is not None and signature is not None:
            self.change_key(scales, signature)

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

        scale_list = normalize_scale_argument(scales)
        for scale in scale_list:
            self[scale] += factor

    def factor_for_key(self, key):
        """音階に対する周波数を返す

        調を変更している場合は調を変えた後の周波数を返す
        key : D3などの音名
        """
        factor = self.__class__.BASE_KEY_FACTOR[key] + self[key]
        return factor

    @classmethod
    def merge(cls, key_conf1, key_conf2):
        """2つのKeyConfig関数を取ってそれを合計したKeyConfigを返す"""

        key_conf1 = key_conf1 or KeyConfig()
        key_conf2 = key_conf2 or KeyConfig()

        new_key_conf = KeyConfig()
        for key in new_key_conf.keys():
            new_key_conf[key] += key_conf1[key] + key_conf2[key]
        return new_key_conf


class MusicComponent(object):
    """generate_wave()関数をもつクラスの抽象クラス"""

    def generate_wave(self, bpm, rate, key_conf):
        """波形生成する関数

        bpm, rate, KeyConfigインスタンスからそのMusicComponentが表す音の
        波形表現を生成する
        bpm : 一分間に４分音符が何回あるか
        rate : 波形のサンプルレート
        key_conf : 調を表すKeyConfigインスタンス
        """
        raise NotImplementedError


class Rest(MusicComponent):
    """休符を表すクラス"""

    def __init__(self, length=1):
        """lenght: 休符の長さ"""

        self.length = length

    def generate_wave(self, bpm, rate, key_conf=None):
        zero_wave = np.zeros(int(self.length * (60 / bpm) * rate))
        return zero_wave


class Note(MusicComponent):
    """単一の音符を表すクラス"""

    def __init__(self, scale, length=1):
        """イニシャライザ

        scale : 音名 ("D3", "c#5" など)
        lenght : 休符の長さ
        """

        super().__init__()

        self.scale = scale
        self.length = length

    def generate_wave(self, bpm, rate, key_conf=None):
        freq = self._freq_from_scale(self.scale, key_conf)

        step = (2 * math.pi) * freq / rate  # 2πf*(1/rate)
        wave = np.sin(
            step *
            np.arange(int(self.length * (60 / bpm) * rate)))  # sin(2πft)
        # wave *= np.linspace(1.5, 0.3, len(wave))
        # rv = scipy.stats.beta(1.5, 3) # ベータ分布の形を使って音を滑らかにする
        rv = scipy.stats.lognorm(1.5)  # 対数正規分布の形を使って音を滑らかにする
        wave *= rv.pdf(np.linspace(0, 1, len(wave)))
        return wave

    def _freq_from_scale(self, scale, key_conf):
        """単一のscaleに対する周波数を返す

        例： "c#5" -> 554.365, "a5"-> 880.000
        """
        key_conf = key_conf or KeyConfig()

        # 正規表現で音階，変化記号，オクターブ番号を抽出
        match = re.match(r'([a-gA-G])([b#]?)([0-9]+)$', scale)
        if match is None:
            raise Exception
        key, accidental, octave_str = match.groups()

        factor = key_conf.factor_for_key(key.upper())
        octave = int(octave_str)

        if accidental == '#':
            factor += 1
        elif accidental == 'b':
            factor -= 1

        freq = 440 * (2**((octave - 4) + factor / 12))
        return freq


class Chord(MusicComponent):
    """MusicComponentクラスのインスタンスを五線譜上で縦に結合するクラス

    同じ長さのNoteを結合すると和音になる
    """

    def __init__(self, components=None, key_conf=None):
        super().__init__()

        self.components = components or []
        self.key_conf = key_conf

    def add(self, component):
        self.components.append(component)

    def generate_wave(self, bpm, rate, base_key_conf=None):
        key_conf = KeyConfig.merge(self.key_conf, base_key_conf)
        waves = [c.generate_wave(bpm, rate, key_conf) for c in self.components]
        wave = functools.reduce(merge_wave, waves)
        return wave


class Series(MusicComponent):

    def __init__(self, components=None, key_conf=None):
        super().__init__()

        self.components = components or []
        self.key_conf = key_conf

    def add(self, component):
        self.components.append(component)

    def add_tone(self, scales, length=1):
        scale_list = normalize_scale_argument(scales)
        chord = Chord([Note(scale, length) for scale in scale_list])
        self.components.append(chord)

    def add_rest(self, length=1):
        self.components.append(Rest(length))

    def generate_wave(self, bpm, rate, base_key_conf=None):
        key_conf = KeyConfig.merge(self.key_conf, base_key_conf)
        waves = [c.generate_wave(bpm, rate, key_conf) for c in self.components]
        wave = np.concatenate(waves)
        return wave


class Music(object):

    def __init__(self, component, bpm=90, rate=44100):
        self.bpm = bpm
        self.rate = rate
        self.component = component

    def play(self, volume=0.1):
        out_wave = self.component.generate_wave(self.bpm, self.rate) * volume

        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paFloat32, channels=1, rate=self.rate,
                         output=True)
        stream.write(out_wave.astype(np.float32).tostring())


def tone(scales, length=1):
    scale_list = normalize_scale_argument(scales)
    chord = Chord([Note(scale, length) for scale in scale_list])
    return chord


def rest(length=1):
    return Rest(length)


def amazing_grace(bpm=120):
    part = Series(
        components=[
            tone(['d4', 'b3']),
            tone(['g4', 'b3'], 2),
            Chord([
                Series([tone('b4', 0.5), tone('g4', 0.5)]),
                tone('d4', 1),
            ]),
            tone(['b4', 'd4'], 2),
            tone(['a4', 'c4']),
            tone(['g4', 'b3'], 2),
            tone(['e4', 'c4']),
            tone(['d4', 'b3'], 2)
        ],
        key_conf=KeyConfig('F', '#'),)

    music = Music(part, bpm=bpm)
    return music


def canon(bpm=90):
    """パッヘルベルのカノンのMusicインスタンスを作成する関数"""

    treble_part = Series(key_conf=KeyConfig(['C', 'F'], '#'))
    bass_part = Series(key_conf=KeyConfig(['A', 'E'], '#'))

    # treble part
    treble_part.add_tone(['f4', 'd4'], 2)
    treble_part.add_tone(['e4', 'c4'], 2)
    treble_part.add_tone(['d4', 'b3'], 2)
    treble_part.add_tone(['c4', 'a3'], 2)

    treble_part.add_tone(['b3', 'g3'], 2)
    treble_part.add_tone(['a3', 'f3'], 2)
    treble_part.add_tone(['b3', 'g3'], 2)
    treble_part.add_tone(['c4', 'a3'], 2)

    treble_part.add_tone(['d5', 'f4'], 2)
    treble_part.add_tone(['c5', 'a4'], 2)
    treble_part.add_tone(['b4', 'd4'], 2)
    treble_part.add_tone(['a4', 'f4'], 2)

    treble_part.add_tone(['g4', 'b3'], 2)
    treble_part.add_tone(['f4', 'd4'], 2)
    treble_part.add_tone(['g4', 'b3'], 2)
    treble_part.add_tone(['a4', 'c4'], 2)

    # bass part
    bass_part.add_tone('d3', 2)
    bass_part.add_tone('a2', 2)
    bass_part.add_tone('b2', 2)
    bass_part.add_tone('f3', 2)
    bass_part.add_tone('g3', 2)
    bass_part.add_tone('d3', 2)
    bass_part.add_tone('g3', 2)
    bass_part.add_tone('f3', 2)

    bass_part.add_tone('d3')
    bass_part.add_tone('f3')
    bass_part.add_tone('a3')
    bass_part.add_tone('g3')
    bass_part.add_tone('f3')
    bass_part.add_tone('d3')
    bass_part.add_tone('f3')
    bass_part.add_tone('e3')

    bass_part.add_tone('d3')
    bass_part.add_tone('b2')
    bass_part.add_tone('d3')
    bass_part.add_tone('a2')
    bass_part.add_tone('g2')
    bass_part.add_tone('b2')
    bass_part.add_tone('c3')
    bass_part.add_tone('a2')
    bass_part.add_rest()

    score = Chord()
    score.add(treble_part)
    score.add(bass_part)

    music = Music(score, bpm=bpm)

    return music


def jupiter(bpm=80):
    part = Series(key_conf=KeyConfig(['A', 'B', 'E'], 'b'))
    part.add_tone('g3', .5)
    part.add_tone('b3', .5)

    part.add_tone(['c4', 'a3'])
    part.add_tone('c4', .5)
    part.add_tone('e4', .5)
    part.add_tone(['d4', 'a3'], .75)
    part.add_tone('b3', .25)

    part.add_tone(['e4', 'b3'], .5)
    part.add_tone('f4', .5)
    part.add_tone('e4')
    part.add_tone(['d4', 'b3'])

    part.add_tone(['c4', 'a3'], .5)
    part.add_tone('d4', .5)
    part.add_tone('c4')
    part.add_tone(['b3', 'f3'])

    part.add_tone(['g3', 'e3'], 2)
    part.add_rest()

    music = Music(part, bpm=bpm)
    return music


def main():
    ag = amazing_grace()
    ag.play()
    # ag.bpm = 180
    # ag.play()

    cn = canon()
    cn.play()

    jp = jupiter()
    jp.play()


if __name__ == '__main__':
    main()
