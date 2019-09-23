import json
import requests
import time
import threading
import queue
import logging

try:
    cbp = open('contributors.bp')
    tasks = json.load(cbp)
except:
    cbp = open('contributors.bp','w')
    tasks = []
    json.dump(tasks,cbp)
finally:
    cbp.close()


index = 0
repos = []
with open('repos.json') as rj:
    j = json.load(rj)
    for i in range(len(j)):
        repos.append(j[i]['full_name'])
        if j[i]['full_name'] in tasks:
            index = i
    print(len(repos))

print(index)

auth_accounts = [
    """
    Github accounts for authentication
    Format:
        (username,password)
    """
]

logging.basicConfig(filename='contributors.log',level=logging.CRITICAL,
format='%(asctime)s %(filename)s %(levelname)s %(threadName)s %(message)s')


def saving(repo,contributors,tasks):
    with open('contributors.json','a') as cj:
        json.dump({
            'repo':repo,
            'contributors':contributors
        },cj)
        cj.write('\n')
    tasks.remove(repo)
    with open('contributors.bp','w') as cbp:
        json.dump(tasks,cbp)


def main(repo,auth_account,proc_cnt):

    page = 1
    contributors = []
    while True:
        for i in range(5):
            try:
                r = requests.get('https://api.github.com/repos/'+repo+"/contributors?per_page=100&page="+str(page),auth=auth_account)
                break
            except Exception as e:
                # logging.exception(e)
                # logging.exception("Connection Error!")
                logging.critical(e)
                # print("Connection Error!")
                if i == 4:
                    return contributors
                time.sleep(10)
        if not r.content:
            j = []
        else:
            j = json.loads(r.content.decode('utf-8'))
        # print(r.headers['X-RateLimit-Remaining'])
        if int(r.headers['X-RateLimit-Remaining']) <= proc_cnt:
            logging.critical("RATE LIMIT EXCEEDED ON ACCOUNT:%s!"%(auth_account[0]))
            while time.time() < int(r.headers['X-RateLimit-Reset']):
                time.sleep(300)
            continue
        if 'message' in j:
            logging.warning(j['message']+'\turl:https://api.github.com/repos/'+repo+"/contributors?per_page=100&page="+str(page))
            break
        if page==1 and len(j)<10:
            break
        if repo != j['full_name']:
            break
        for contr in j:
            contributors.append({
                'login':contr['login'],
                'id':contr['id'],
                'contributions':contr['contributions'],
            })
        if len(j) < 100:
            break
        page += 1
    return contributors




def consumer(task_queue,tasks,result_queue,auth_account,proc_cnt):

    task_cnt = 0
    while True:
        next_task = task_queue.get()
        if next_task is None:
           # Poison pill means shutdown
            logging.warning('Exiting')
            task_queue.task_done()
            break
        repo = next_task
        logging.warning(next_task)
        contrs = main(repo,auth_account,proc_cnt)
        task_queue.task_done() # Must be called the same times as .get()
        if contrs:
            result_queue.put([repo,contrs])
        else:
            tasks.remove(repo)
        task_cnt += 1
        if task_cnt%1000 == 1:
            logging.critical("ALIVE")


def producer(repos,ind,task_queue,tasks,proc_cnt):

    for i in range(ind,len(repos)):
        repo = repos[i]
        task_queue.put(repo)
        tasks.append(repo)
    for i in range(proc_cnt):
        task_queue.put(None)

task_queue = queue.Queue(maxsize=10)
result_queue = queue.Queue(maxsize=10)
proc_cnt = len(auth_accounts)*2

threads = []
for i in range(proc_cnt):
    t = threading.Thread(target=consumer,name="Thread#"+str(i+1),args=(task_queue,tasks,result_queue,auth_accounts[i//2],2),daemon=True)
    threads.append(t)
    t.start()

for t in tasks:
    task_queue.put(t)
t = threading.Thread(target=producer,args=(repos,index+1,task_queue,tasks,proc_cnt),daemon=True)
t.start()

while True:
    try: 
        repo,contrs = result_queue.get(timeout=600)
    except:
        break
    saving(repo,contrs,tasks)
    result_queue.task_done()