"""Run RAGAS against actual retrieval and graph outputs; never fabricate demo scores."""
import argparse
import asyncio
import json
import math
import sys
from pathlib import Path
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.embeddings import embedding_factory
from ragas.metrics.collections import ContextPrecision, ContextRecall, Faithfulness, AnswerRelevancy, FactualCorrectness
from app.config import settings
from app.store import init, authorize
from app.rag import retrieve, rag_graph

async def run(args):
    cases=[json.loads(line) for line in Path(args.dataset).read_text().splitlines() if line.strip()]
    for case in cases:
        if not all(isinstance(case.get(k),str) and case[k].strip() for k in ('question','reference')):
            raise ValueError('Each case requires a question and a human-reviewed reference')
    if not cases:
        raise ValueError('Evaluation dataset is empty')
    if args.validate_only:
        print(f'Validated {len(cases)} cases and RAGAS imports. No model calls or evaluation scores.')
        return
    if settings.demo_mode or not settings.openai_api_key:
        raise ValueError('RAGAS scoring requires DEMO_MODE=false and a configured OPENAI_API_KEY')
    init();authorize(args.notebook,args.user)
    client=AsyncOpenAI(api_key=settings.openai_api_key,base_url=settings.openai_base_url)
    judge=llm_factory(args.judge_model or settings.chat_model,client=client)
    embeddings=embedding_factory('openai',model=settings.embedding_model,client=client)
    precision,recall=ContextPrecision(llm=judge),ContextRecall(llm=judge)
    faithfulness,relevance,correctness=Faithfulness(llm=judge),AnswerRelevancy(llm=judge,embeddings=embeddings),FactualCorrectness(llm=judge)
    results=[]
    for case in cases:
        q,ref=case['question'],case['reference']
        initial=await retrieve(args.notebook,args.user,q)
        contexts=[h['text'] for h in initial]
        if not contexts:raise ValueError('Notebook has no processed sources')
        component={
            'context_precision':float(await precision.ascore(user_input=q,reference=ref,retrieved_contexts=contexts)),
            'context_recall':float(await recall.ascore(user_input=q,reference=ref,retrieved_contexts=contexts))}
        result={'question':q,'reference':ref,'component':component,'initial_contexts':contexts}
        if args.mode=='all':
            state=await rag_graph.ainvoke({'user':args.user,'notebook':args.notebook,'question':q,'history':[]},config={'tags':['evaluation']})
            final_contexts=[h['text'] for h in state['hits']]
            result.update({'response':state['answer'],'final_contexts':final_contexts,'hops':state['hop'],'end_to_end':{
                'faithfulness':float(await faithfulness.ascore(user_input=q,response=state['answer'],retrieved_contexts=final_contexts)),
                'answer_relevancy':float(await relevance.ascore(user_input=q,response=state['answer'])),
                'factual_correctness':float(await correctness.ascore(reference=ref,response=state['answer']))}})
        for group in ('component','end_to_end'):
            if any(not math.isfinite(v) for v in result.get(group,{}).values()):
                raise ValueError('Evaluator produced non-finite scores; inspect dataset/model responses')
        results.append(result)
    summary={group:{metric:sum(r[group][metric] for r in results)/len(results) for metric in results[0][group]} for group in ('component','end_to_end') if group in results[0]}
    output={'model':settings.chat_model,'judge':args.judge_model or settings.chat_model,'embedding':settings.embedding_model,'summary':summary,'cases':results}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(output,indent=2))
    print(json.dumps(summary,indent=2))
    if args.min_faithfulness is not None and summary.get('end_to_end',{}).get('faithfulness',0)<args.min_faithfulness:
        sys.exit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--dataset',default='evaluation/cases.jsonl')
    p.add_argument('--notebook',default='')
    p.add_argument('--user',choices=['alice','bob'],default='alice')
    p.add_argument('--mode',choices=['components','all'],default='all')
    p.add_argument('--judge-model')
    p.add_argument('--output',default='data/evaluation/report.json')
    p.add_argument('--min-faithfulness',type=float)
    p.add_argument('--validate-only',action='store_true')
    asyncio.run(run(p.parse_args()))
