from transformers import pipeline
import itertools
from math import sqrt, floor
import pandas as pd
from datetime import datetime
from time import time
from argparse import ArgumentParser

parser = ArgumentParser(description= "Zero Shot Approach for Binary Classification")
parser.add_argument("-t", "--text", help='Enter the filepath of an excel file containing text sequence. Required columns:"id","text_sequence". Sheet Name: "text_seq"', required=True)
parser.add_argument("-l", "--labels", help='Enter the filepath of an excel file containing labels. Required columns:"category1","category2". Sheet Name: "labels"', required=True)
parser.add_argument("-c", "--confidence", type=float, help='Enter the Confidence Level value between 0 to 1', required=True)
parser.add_argument("-cer", "--certainty", type=float,  help='Enter the Certainty Level value greater than 0', required=True)
parser.add_argument("-a", "--agg", help='Enter the aggregation method to be used. Accepted values: "Sum", "Ordered Sum", "Label Mean", "Ordered Label Mean"', required=True)
parser.add_argument("-o", "--output", help='(Optional) Enter the output file name. Default: "Predictions.xlsx"', required=False, default="Predictions.xlsx")
args = parser.parse_args()
data = pd.read_excel(args.text, sheet_name="text_seq")

labels = pd.read_excel(args.labels, sheet_name="labels")

category1 = labels["category1"].tolist()
category2 = labels["category2"].tolist()

confidence_level = args.confidence

certainty_level = args.certainty

aggregation_method = args.agg

filename = args.output

def label_mean(result_cat):
    agg = 0
    for label in result_cat.values():
        agg += (sum(label)/len(label))
    return agg

def order_premutations(category1, category2):
    # m = length of category with maximum labels
    # n = length of category with minimum labels
    # mi = index of category 1 starting from 0
    # ni = index of category 2 starting from 0
    # formula mi+ni+(n*mi)(- n : if mi+ni >= n)

    max_category = category1 if len(category1) >= len(category2) else category2
    min_category = category2 if len(category1) >= len(category2) else category1

    permutations = list(itertools.product(max_category, min_category))

    m = len(max_category)
    n = len(min_category)
    ordered_premutations = []
    for ni in range(n):
        for mi in range(m):
            if mi+ni < n:
                ordered_premutations.append(tuple(reversed(permutations[mi+ni+(n*mi)])) if len(category2) > len(category1) else  permutations[mi+ni+(n*mi)])
            else:
                ordered_premutations.append(tuple(reversed(permutations[mi+ni+(n*mi)-(n*floor((mi+ni)/n))])) if len(category2) > len(category1) else permutations[mi+ni+(n*mi)-(n*floor((mi+ni)/n))])
    return ordered_premutations


# agg. : label mean of results
# result class : greater than certainty_level
def make_predictions_label_mean(id, sequence, permutations, confidence_level, certainty_level):
    result_cat1 = {}
    result_cat2 = {}
    sum_cat1 = 0
    sum_cat2 = 0
    for p in permutations:
        result = classifier(sequence, list(p),hypothesis_template="{}")
        result_dict = dict(zip(result['labels'],result['scores']))
        if abs(result_dict[p[0]]- result_dict[p[1]]) < confidence_level:
            continue
        result_cat1.setdefault(p[0], []).append(result_dict[p[0]])
        result_cat2.setdefault(p[1], []).append(result_dict[p[1]])

        # aggregation
        sum_cat1 = label_mean(result_cat1)
        sum_cat2 = label_mean(result_cat2)

        if sum_cat1 > certainty_level and sum_cat2 > certainty_level:
            return { "id": id,  "text_sequence": sequence, "predictions": "1"} if sum_cat1 > sum_cat2 else { "id": id,  "text_sequence": sequence, "predictions": "2"}
        elif sum_cat1 > certainty_level:
            return { "id": id,  "text_sequence": sequence, "predictions": "1"}
        elif sum_cat2 > certainty_level:
            return { "id": id,  "text_sequence": sequence, "predictions": "2"}
    return { "id": id,  "text_sequence": sequence, "predictions": "Undecided"}



# agg. : sum of results
# result class : greater than certainty_level
def make_predictions_sum_results(id, sequence, permutations, confidence_level, certainty_level):
    result_cat1 = []
    result_cat2 = []
    sum_cat1 = 0
    sum_cat2 = 0
    for p in permutations:
        result = classifier(sequence, list(p), hypothesis_template="{}")
        result_dict = dict(zip(result['labels'],result['scores']))
        if abs(result_dict[p[0]]- result_dict[p[1]]) < confidence_level:
            continue
    
        result_cat1.append(result_dict[p[0]])
        result_cat2.append(result_dict[p[1]])

        # aggregation
        sum_cat1 = sum(result_cat1)
        sum_cat2 = sum(result_cat2)

        if sum_cat1 > certainty_level and sum_cat2 > certainty_level:
            return { "id": id,  "text_sequence": sequence, "predictions": "1"} if sum_cat1 > sum_cat2 else { "id": id,  "text_sequence": sequence, "predictions": "2"}
        elif sum_cat1 > certainty_level:
            return { "id": id,  "text_sequence": sequence, "predictions": "1"}
        elif sum_cat2 > certainty_level:
            return { "id": id,  "text_sequence": sequence, "predictions": "2"}
    return { "id": id, "text_sequence": sequence,  "predictions": "Undecided"}

# classifier = pipeline("zero-shot-classification", model='joeddav/xlm-roberta-large-xnli', device=2)
classifier = pipeline("zero-shot-classification", model='/home/nikhil/zeroshot/model', device=2)


data_predictions = []

permutations = itertools.product(category1, category2)

for sequence in data.itertuples():
    email = sequence.text_sequence
    result_cat1 = []
    result_cat2 = []
    sum_cat1 = 0
    sum_cat2 = 0

    if aggregation_method == "Sum":
        data_predictions.append(make_predictions_sum_results(sequence.id, sequence.text_sequence, permutations, confidence_level, certainty_level))
    elif aggregation_method == "Ordered Sum":
        data_predictions.append(make_predictions_sum_results(sequence.id, sequence.text_sequence, order_premutations(category1, category2), confidence_level, certainty_level))
    elif aggregation_method == "Label Mean":
        data_predictions.append(make_predictions_label_mean(sequence.id, sequence.text_sequence, permutations, confidence_level, certainty_level))
    elif aggregation_method == "Ordered Label Mean":
        data_predictions.append(make_predictions_label_mean(sequence.id, sequence.text_sequence, order_premutations(category1, category2), confidence_level, certainty_level))

data_predictions_df = pd.DataFrame(data_predictions).to_excel(filename)
print("Results saved successfully")