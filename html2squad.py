import json
import os
from pathlib import Path

import bs4
import jsonlines
from bs4 import BeautifulSoup

# Paths to all the required files
target_dir = "squad2_fi/"
if not os.path.exists(target_dir):
    os.mkdir(target_dir)
path_to_raw_html = "squad2-fi-raw/html/"
path_to_full_json = "squad2_fi/squad2_fi.json"
path_to_dev_json = "squad2_fi/dev-v2.0.json"
path_to_train_json = "squad2_fi/train-v2.0.json"

# colors from palette.txt for easier access
colors = ['#696969', '#a9a9a9', '#dcdcdc', '#2f4f4f', '#556b2f', '#6b8e23', '#a0522d', '#228b22', '#191970', '#8b0000', '#483d8b', '#3cb371', '#bc8f8f', '#663399', '#008080', '#bdb76b', '#4682b4', '#d2691e', '#9acd32', '#cd5c5c', '#00008b', '#32cd32', '#daa520', '#7f007f', '#8fbc8f', '#b03060', '#66cdaa', '#9932cc', '#ff4500', '#00ced1', '#ff8c00', '#ffd700',
          '#c71585', '#0000cd', '#deb887', '#00ff00', '#00ff7f', '#4169e1', '#e9967a', '#dc143c', '#00ffff', '#00bfff', '#f4a460', '#9370db', '#0000ff', '#a020f0', '#adff2f', '#ff6347', '#da70d6', '#d8bfd8', '#ff00ff', '#db7093', '#f0e68c', '#ffff54', '#6495ed', '#dda0dd', '#90ee90', '#87ceeb', '#ff1493', '#afeeee', '#7fffd4', '#ff69b4', '#ffe4c4', '#ffb6c1']


def is_bu(elem):  # is this a bold_underline?
    return len(list(elem.select("u > b"))) > 0 or len(list(elem.select("b > u"))) > 0


def is_b(elem):  # is this bold?
    return len(list(elem.select("b"))) > 0


def is_tag(elem):
    return isinstance(elem, bs4.Tag)


def get_answer(tag):
    ans = tag.get_text().replace("\n", " ")
    return ans


"""
Get location of each <font> tag in paragraph and then subtract index * 29 from
each (font tag has 29 characters in total) to fix the offset caused by the
tags themselves.
"""


def get_ans_pos(para, colors):
    positions = []
    para = str(para)
    # These all mess up the indexing
    para = para.replace("&amp;", " ").replace('&lt;', " ").replace('&gt;', " ")
    para = para.replace('<font face="ＭＳ 明朝">', "")  # Chinese text tag
    para = para.replace('</font>', "")  # Replace all closing font tags
    para = para.replace('<font face=""><span lang="ar-SA">',
                        "").replace('</span>', "")
    para = para.replace('<br/>', "")  # line break
    # print(para) # print the whole paragraph with tags to make sense of this all
    font_tag = 22  # Length of the opening font tag
    color_start = 13  # Length from the color to the start of the font tag
    p_tag = 33  # length of the p tag in the start of the string
    tags_len = color_start + p_tag
    for i, color in enumerate(colors):
        # Get the positions of the answers in plain text paragraphs
        index = para.find(color)-font_tag*i-tags_len
        # Prevent indexing the same tag twice when there is multiple tags with
        # the same color.
        para = para.replace(color, '#######', 1)
        positions.append(index)
    return positions


titles = []
meta_ids = []
meta_qas = []
title_counter = 0
counter = 0
with jsonlines.open('squad2-en/meta.jsonl', 'r') as squad:
    lines = [obj for obj in squad]
    for doc in lines:
        titles.append(doc['title'])
        for para in doc["paragraphs"]:
            for question in para[2]:
                meta_ids.append(question)

    for title in lines:
        for para in title["paragraphs"]:
            for id, color in para[1].items():
                if color == -1:
                    pass
                elif '+' in id:
                    id_list = id.split('+')
                    for id in id_list:
                        ques, ans = id.split('_')
                        meta_qas.append([ques, int(ans), color])
                else:
                    ques, ans = id.split('_')
                    meta_qas.append([ques, int(ans), color])

impossibles = []
with open('squad2-en/dev-v2.0.json', 'r') as dev, open('squad2-en/train-v2.0.json', 'r') as train:
    dev = json.loads(dev.read())
    train = json.loads(train.read())
    for line in train['data']:
        for line in line['paragraphs']:
            for line in line['qas']:
                impossibles.append([line['id'], line['is_impossible']])
    for line in dev['data']:
        for line in line['paragraphs']:
            for line in line['qas']:
                impossibles.append([line['id'], line['is_impossible']])


json_dict = {
    "version": "v2.0",
    "data": []
}
for file in sorted(Path(path_to_raw_html).glob('*.html')):
    with open(file, 'r') as file:
        soup = BeautifulSoup(file, 'html.parser')
        questions = []

        for elem in soup.body.children:
            if not is_tag(elem):
                continue

            # Get the document ID's
            if is_bu(elem):
                title = titles[title_counter]
                title_counter += 1
                title_dict = {
                    "title": title,
                    "paragraphs": []
                }
                json_dict["data"].append(title_dict)
                doc_id = int(
                    ''.join([i for i in elem.get_text().split() if i.isdigit()]))
                continue

            # Get the answers
            if is_b(elem) and "numero" in elem.get_text():
                para_id = int(
                    ''.join([i for i in elem.get_text().split() if i.isdigit()]))
                para = elem.find_next("p")
                para_str = para.get_text().replace("\n", " ")
                ans_colors = []
                color_ids = []
                answers = []
                answer_pos = []
                for tag in para("font"):
                    # Replace non-answer font-tags with plain text
                    if tag.get("color") is None:
                        tag = tag.get_text()
                    else:
                        color = tag['color']
                        # = color id in meta.jsonl
                        color_ids.append(colors.index(color))
                        answers.append(get_answer(tag))
                        ans_colors.append(color)
                        answer_pos = get_ans_pos(para, ans_colors)
                para_dict = {
                    "qas": [],
                    "context": para_str
                }
                json_dict["data"][doc_id]["paragraphs"].append(para_dict)
                continue

            # Get questions
            if is_b(elem) and "Kysymys" in elem.get_text():
                question_str = elem.find_next(
                    "p").get_text().replace("\n", " ")
                ques_id = int(
                    ''.join([i for i in elem.get_text().split() if i.isdigit()]))
                ans_pos_raw = []
                for qa in meta_qas:
                    if qa[0] == meta_ids[counter]:
                        for i, color in enumerate(color_ids):
                            if qa[2] == color_ids[i]:
                                word = answers[i]
                                pos = answer_pos[i]
                                ans_pos_raw.append([qa[1], pos, word])

                if impossibles[counter][1] is True:
                    question_dict = {
                        "plausible_answers": [],
                        "question": question_str,
                        "id": meta_ids[counter],
                        "answers": [],
                        "is_impossible": impossibles[counter][1]
                    }
                else:
                    question_dict = {
                        "question": question_str,
                        "id": meta_ids[counter],
                        "answers": [],
                        "is_impossible": impossibles[counter][1]
                    }
                json_dict["data"][doc_id]["paragraphs"][para_id]["qas"].append(
                    question_dict)

                answers_str = []
                ans_pos_raw = sorted(ans_pos_raw)
                for i, answer in enumerate(ans_pos_raw):
                    if i == 0:
                        answers_str.append([answer[0], answer[2], answer[1]])
                    elif answer[0] != ans_pos_raw[i-1][0]:
                        answers_str.append([answer[0], answer[2], answer[1]])
                    else:
                        for ans in answers_str:
                            if ans[0] == answer[0]:
                                ans[1] += answer[2]

                for answer in answers_str:
                    answer_dict = {
                        "text": answer[1].strip(" .,-:"),
                        "answer_start": answer[2],
                        "texts": [text[2] for text in sorted(ans_pos_raw) if text[0] == answer[0]],
                        "starts": [text[1] for text in sorted(ans_pos_raw) if text[0] == answer[0]]
                    }
                    all_answer_starts_dict = {
                        "separate_answer_starts": ans_pos_raw
                    }
                    if impossibles[counter][1] is True:
                        json_dict["data"][doc_id]["paragraphs"][para_id]["qas"][ques_id]["plausible_answers"].append(
                            answer_dict)
                    else:
                        json_dict["data"][doc_id]["paragraphs"][para_id]["qas"][ques_id]["answers"].append(
                            answer_dict)
                counter += 1


# Create one full json file with all data
with open(path_to_full_json, "w") as json_file:
    json.dump(json_dict, json_file)


# Split full json file into dev & train
dev_dict = {
    "version": "v2.0",
    "data": []
}

train_dict = {
    "version": "v2.0",
    "data": []
}

with open(path_to_full_json, "r") as in_file:
    squad_fi = json.loads(in_file.read())
    count = 0
    for line in squad_fi["data"]:
        if count < 442:
            train_dict["data"].append(line)
        if count >= 442:
            dev_dict["data"].append(line)
        count += 1

with open(path_to_dev_json, "w") as dev_file:
    json.dump(dev_dict, dev_file)

with open(path_to_train_json, "w") as train_file:
    json.dump(train_dict, train_file)
