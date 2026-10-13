import test from 'node:test';
import assert from 'node:assert/strict';
import { stream,request } from '../src/api.ts';

test('chat retries a gateway rejection and consumes the recovered SSE response',async(t)=>{
  const calls=[];
  t.mock.method(globalThis,'fetch',async(url,options)=>{
    calls.push({url,body:options.body});
    if(calls.length===1)return new Response('Bad Gateway',{status:502});
    return new Response('data: {"type":"token","text":"hello"}\n\ndata: {"type":"done"}\n\n');
  });
  const events=[];
  await stream('/notebooks/n/chat','test-token',{method:'POST',body:'{"question":"alo"}'},e=>events.push(e));
  assert.equal(calls.length,2);
  assert.equal(calls[0].body,calls[1].body);
  assert.deepEqual(events,[{type:'token',text:'hello'},{type:'done'}]);
});

test('cancelling during restart backoff prevents another chat request',async(t)=>{
  let calls=0;
  const controller=new AbortController();
  t.mock.method(globalThis,'fetch',async()=>{
    calls++;setTimeout(()=>controller.abort(),10);
    return new Response('Unavailable',{status:503});
  });
  await assert.rejects(stream('/chat','test',{signal:controller.signal},()=>{}),{name:'AbortError'});
  assert.equal(calls,1);
});

test('authentication errors are not retried',async(t)=>{
  let calls=0;
  t.mock.method(globalThis,'fetch',async()=>{calls++;return new Response('',{status:401});});
  await assert.rejects(stream('/chat','test',{},()=>{}),{status:401});
  assert.equal(calls,1);
});

test('a stream failure after acceptance is not replayed',async(t)=>{
  let calls=0;
  t.mock.method(globalThis,'fetch',async()=>{
    calls++;
    return new Response(new ReadableStream({start(c){c.error(new TypeError('Connection lost'));}}));
  });
  await assert.rejects(stream('/chat','test',{},()=>{}),/Connection lost/);
  assert.equal(calls,1);
});

test('other POST requests are not automatically replayed',async(t)=>{
  let calls=0;
  t.mock.method(globalThis,'fetch',async()=>{calls++;return new Response('Bad Gateway',{status:502});});
  await assert.rejects(request('/notebooks','test',{method:'POST',body:'{}'}),{status:502});
  assert.equal(calls,1);
});

test('gateway retries stop after four attempts',async(t)=>{
  t.mock.timers.enable({apis:['setTimeout']});
  let calls=0;
  t.mock.method(globalThis,'fetch',async()=>{calls++;return new Response('Timeout',{status:504});});
  const rejected=assert.rejects(stream('/chat','test',{},()=>{}),{status:504});
  for(const delay of [1000,2000,4000]){
    await new Promise(resolve=>setImmediate(resolve));
    t.mock.timers.tick(delay);
  }
  await rejected;
  assert.equal(calls,4);
});
