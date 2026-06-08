import json
import base64
import time
import os
from prompt_loader import get_full_prompt
import pandas as pd
import random
import genanki
from typing import List
from pydantic import BaseModel
from google.genai import types

class VocabItem(BaseModel):
    mot_original: str
    lecture: str
    traduction: str
    precision: str
    kanji: str

class VocabList(BaseModel): # double wrapper pour le schema du google de ses morts
    vocabulaire: List[VocabItem]

class VocPipeline:
    def __init__(self, model_loader):
        self.loader = model_loader

    def extract_vocab(self, image_path, autocorrect=False):
        system_prompt = get_full_prompt(autocorrect=autocorrect) 
        
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        imagepart = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        
        try:
            response = self.loader.client.models.generate_content(
                model=self.loader.model_name,
                contents=[
                    imagepart,
                    "Extrais le vocabulaire de l'image en suivant le format JSON demandé."
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=VocabList,
                )
            )
            
            if response.parsed:
                return [item.model_dump() for item in response.parsed.vocabulaire]
            return []

        except Exception as e:
            print(f"erreur schema: {e}")
            return self._fallback_extract(imagepart, system_prompt)

        
    def save_to_apkg(self, data, output_name="deck.apkg", deck_id = 0):
        if not data:
            print("Pas de data en export")
            return

        model_id = random.randrange(1 << 30, 1 << 31) #TODO ajouter une option pour fixer?
        my_model = genanki.Model(
            model_id,
            'Vocab Model',
            fields=[
                {'name': 'Question'},
                {'name': 'Answer'},
                {'name': 'Precision'},
                {'name': 'Kanji'},
            ],
            templates=[
                {
                    'name': 'Card 1',
                    'qfmt': '<div style="font-size: 30px; text-align: center;">{{Question}}</div>',
                    'afmt': '''{{FrontSide}}<hr id="answer">
                               <div style="text-align: center;">{{Answer}}</div>
                               {{#Precision}}
                               <div style="font-size: 16px; color: #7f8c8d; font-style: italic; margin-top: 10px;">
                                 Note : {{Precision}}
                               </div>
                               {{/Precision}}
                               {{#Kanji}}
                               <div style="font-size: 15px; color: #8e44ad; margin-top: 14px;">
                                 <div style="font-weight: bold; margin-bottom: 4px;">漢字情報</div>
                                 {{Kanji}}
                               </div>
                               {{/Kanji}}''',
                },
            ],
            css='.card { font-family: arial; font-size: 20px; text-align: center; color: black; background-color: white; }'
        )

        if deck_id == 0: # signal default
            deck_id = random.randrange(1 << 30, 1 << 31)
        deck_name = output_name.replace(".apkg", "")
        my_deck = genanki.Deck(deck_id, deck_name)

        for item in data:
            original = item.get("mot_original", "")
            lecture = item.get("lecture", "")
            traduction = item.get("traduction", "")
            precision = item.get("precision", "")
            kanji = item.get("kanji", "")
            
            answer_html = f"<div style='color: #2ecc71; font-size: 25px;'>{lecture}</div><br>{traduction}"
            
            my_note = genanki.Note(
                model=my_model,
                fields=[original, answer_html, precision, kanji]
            )
            my_deck.add_note(my_note)

        try:
            genanki.Package(my_deck).write_to_file(output_name)
            print(f"Finito : {output_name} ({len(data)} cartes)")
        except Exception as e:
            print(f"Erreur package : {e}")