import os
import time
import argparse

from tqdm import tqdm

from src.utils import read_file
from src.utils import read_nbest
from src.utils import write_file

from src.detection.bert_detector  import BertDetector
from src.detection.ckip_detector  import CkipDetector
from src.detection.nbest_detector import NbestDetector
from src.detection.cheat_detector import CheatDetector

from src.retrieval.pinyin_retriever import PinyinRetriever

from src.rejection.nbest_rejector import NbestRejector

OUTPUT_DIR = './dump'

def NameEntityCorrector(args, texts, detector, retriever, nbests=None, nbest_detector=None):
    if args.detection_model_type == "cheat_detector":
        ref_texts = read_file(args.asr_manuscript_path, sp=' ')
        ref_texts = [" ".join(data[1:]) for data in ref_texts]
        predictions = detector.predict(ref_texts, texts)
    else:
        predictions = detector.predict(texts)
    
    if args.use_rejection:
        predictions_nbest = nbest_detector.predict_no_detect(texts, nbests, predictions)
    final_texts = []
    for i, prediction in tqdm(enumerate(predictions)):
        entities  = [entity for entity, entity_type, position in prediction]
        results   = retriever.retrieve(entities)
        candiates = [result[0][1] for result in results]

        if args.use_rejection:
            candiates = NbestRejector.reject(prediction, predictions_nbest[i], candiates)

        now, final_text = 0, []
        for candiate, predict in zip(candiates, prediction):
            _, _, position = predict
            start, end = position
            final_text += f'{texts[i][now:start]}{candiate}'
            now = end
        final_text += texts[i][now:]
        final_texts.append("".join(final_text))
    return final_texts

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--asr_transcription_path"      ,  type=str, required=True)
    parser.add_argument("--asr_manuscript_path"         ,  type=str, required=False)

    parser.add_argument("--detection_model_type"        ,  type=str, required=True)
    parser.add_argument("--detection_model_path"        ,  type=str, required=True)
    
    parser.add_argument("--retrieval_model_type"        ,  type=str, required=True)
    parser.add_argument("--entity_path"                 ,  type=str, required=True)

    parser.add_argument("--use_rejection"               ,  type=str, required=True)
    parser.add_argument("--asr_nbest_transcription_path",  type=str, required=False)
    parser.add_argument("--rejection_model_path"        ,  type=str, required=False)
    
    args = parser.parse_args()

    asr_texts = read_file(args.asr_transcription_path, sp=' ')
    indexis   = [data[0] for data in asr_texts]
    texts     = [" ".join(data[1:]) for data in asr_texts]
    
    if args.detection_model_type == "bert_detector":
        detector  = BertDetector(args.detection_model_path)
    elif args.detection_model_type == "ckip_detector":
        detector  = CkipDetector(args.detection_model_path)
    elif args.detection_model_type == "cheat_detector":
        detector  = CheatDetector(args.entity_path)

    if args.retrieval_model_type == "pinyin_retriever":
        retriever = PinyinRetriever(args.entity_path)

    args.use_rejection = True if args.use_rejection == "True" else False

    print(args.use_rejection)
    if not args.use_rejection:
        results = NameEntityCorrector(args, texts, detector, retriever)
    else:
        nbests_dict = read_nbest(args.asr_nbest_transcription_path, sp=' ')
        nbests  = [nbests_dict[index][1:] for index, _ in asr_texts]
        # nbest_detector = NbestDetector(model=detector.model)
        nbest_detector = NbestDetector(model="None")
        
        results = NameEntityCorrector(args, texts, detector, retriever, nbests, nbest_detector)

    results = [[index, result] for index, result in zip(indexis, results)]

    time_now = time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime())
    exp_dir  = os.path.join(OUTPUT_DIR, time_now)
    os.mkdir(exp_dir)
    print(f'save to {exp_dir}...')

    res_path = os.path.join(exp_dir, 'hyp')
    write_file(res_path, results)