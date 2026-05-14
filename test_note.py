from music21 import pitch
midi_note = 60
nota_obj = pitch.Pitch(midi=midi_note)
print(nota_obj.nameWithOctave)
