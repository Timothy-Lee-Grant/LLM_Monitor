# Current Status of System

I am able to run my test_start_up.sh . When I do so I am getting:


timothygrant > ./test_start_up.sh 
 1. Aggressively tearing down previous instances of target services...
[+] Running 1/1
 ✔ Volume llm_monitor_ollama_data  Removed                                                  0.0s 
 2. Rebuilding Langchain fresh (bypassing layer cache)...
#1 [internal] load local bake definitions
#1 reading from stdin 661B done
#1 DONE 0.0s

#2 [internal] load build definition from dockerfile
#2 transferring dockerfile: 295B done
#2 DONE 0.0s

#3 [internal] load metadata for docker.io/library/python:3.9.13-slim-buster
#3 DONE 1.3s

#4 [internal] load .dockerignore
#4 transferring context: 2B done
#4 DONE 0.0s

#5 [1/4] FROM docker.io/library/python:3.9.13-slim-buster@sha256:e0bf67a281748c0f00c320dbe522631e92c649bef22a14f00a599c1981dac2a6
#5 CACHED

#6 [internal] load build context
#6 transferring context: 180B done
#6 DONE 0.0s

#7 [2/4] COPY requirements.txt requirements.txt
#7 DONE 0.0s

#8 [3/4] RUN pip install -r requirements.txt
#8 6.991 Collecting flask
#8 7.209   Downloading flask-3.1.3-py3-none-any.whl (103 kB)
#8 7.262      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 103.4/103.4 KB 2.0 MB/s eta 0:00:00
#8 7.438 Collecting langchain-core
#8 7.467   Downloading langchain_core-0.3.86-py3-none-any.whl (461 kB)
#8 7.536      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 461.3/461.3 KB 6.7 MB/s eta 0:00:00
#8 7.687 Collecting langchain-community
#8 7.711   Downloading langchain_community-0.3.31-py3-none-any.whl (2.5 MB)
#8 7.810      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.5/2.5 MB 26.0 MB/s eta 0:00:00
#8 7.924 Collecting langchain-ollama
#8 7.954   Downloading langchain_ollama-0.3.10-py3-none-any.whl (27 kB)
#8 8.000 Collecting jinja2>=3.1.2
#8 8.025   Downloading jinja2-3.1.6-py3-none-any.whl (134 kB)
#8 8.035      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 134.9/134.9 KB 16.7 MB/s eta 0:00:00
#8 8.176 Collecting itsdangerous>=2.2.0
#8 8.197   Downloading itsdangerous-2.2.0-py3-none-any.whl (16 kB)
#8 8.265 Collecting werkzeug>=3.1.0
#8 8.286   Downloading werkzeug-3.1.8-py3-none-any.whl (226 kB)
#8 8.293      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 226.5/226.5 KB 41.1 MB/s eta 0:00:00
#8 8.380 Collecting importlib-metadata>=3.6.0
#8 8.411   Downloading importlib_metadata-8.7.1-py3-none-any.whl (27 kB)
#8 8.536 Collecting markupsafe>=2.1.1
#8 8.562   Downloading markupsafe-3.0.3-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl (21 kB)
#8 8.611 Collecting click>=8.1.3
#8 8.709   Downloading click-8.1.8-py3-none-any.whl (98 kB)
#8 8.713      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 98.2/98.2 KB 44.9 MB/s eta 0:00:00
#8 8.749 Collecting blinker>=1.9.0
#8 8.770   Downloading blinker-1.9.0-py3-none-any.whl (8.5 kB)
#8 8.829 Collecting packaging<26.0.0,>=23.2.0
#8 8.849   Downloading packaging-25.0-py3-none-any.whl (66 kB)
#8 8.852      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 66.5/66.5 KB 33.6 MB/s eta 0:00:00
#8 8.899 Collecting typing-extensions<5.0.0,>=4.7.0
#8 8.920   Downloading typing_extensions-4.15.0-py3-none-any.whl (44 kB)
#8 8.925      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 44.6/44.6 KB 9.5 MB/s eta 0:00:00
#8 9.114 Collecting langsmith<1.0.0,>=0.3.45
#8 9.229   Downloading langsmith-0.4.37-py3-none-any.whl (396 kB)
#8 9.248      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 396.1/396.1 KB 22.3 MB/s eta 0:00:00
#8 9.295 Collecting jsonpatch<2.0.0,>=1.33.0
#8 9.321   Downloading jsonpatch-1.33-py2.py3-none-any.whl (12 kB)
#8 9.579 Collecting pydantic<3.0.0,>=2.7.4
#8 9.635   Downloading pydantic-2.13.4-py3-none-any.whl (472 kB)
#8 9.649      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 472.3/472.3 KB 40.2 MB/s eta 0:00:00
#8 9.826 Collecting tenacity!=8.4.0,<10.0.0,>=8.1.0
#8 9.850   Downloading tenacity-9.1.2-py3-none-any.whl (28 kB)
#8 9.958 Collecting PyYAML<7.0.0,>=5.3.0
#8 9.979   Downloading pyyaml-6.0.3-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl (737 kB)
#8 9.998      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 737.6/737.6 KB 42.3 MB/s eta 0:00:00
#8 10.20 Collecting uuid-utils<1.0,>=0.12.0
#8 10.40   Downloading uuid_utils-0.15.0-cp39-cp39-manylinux_2_17_aarch64.manylinux2014_aarch64.whl (329 kB)
#8 10.42      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 329.7/329.7 KB 28.4 MB/s eta 0:00:00
#8 10.80 Collecting langchain<2.0.0,>=0.3.27
#8 10.84   Downloading langchain-0.3.30-py3-none-any.whl (1.0 MB)
#8 10.86      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.0/1.0 MB 47.7 MB/s eta 0:00:00
#8 10.93 Collecting dataclasses-json<0.7.0,>=0.6.7
#8 10.95   Downloading dataclasses_json-0.6.7-py3-none-any.whl (28 kB)
#8 12.07 Collecting aiohttp<4.0.0,>=3.8.3
#8 12.09   Downloading aiohttp-3.13.5-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl (1.7 MB)
#8 12.13      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.7/1.7 MB 41.1 MB/s eta 0:00:00
#8 12.20 Collecting pydantic-settings<3.0.0,>=2.10.1
#8 12.23   Downloading pydantic_settings-2.11.0-py3-none-any.whl (48 kB)
#8 12.23      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 48.6/48.6 KB 21.5 MB/s eta 0:00:00
#8 12.40 Collecting requests<3.0.0,>=2.32.5
#8 12.42   Downloading requests-2.32.5-py3-none-any.whl (64 kB)
#8 12.42      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 64.7/64.7 KB 28.4 MB/s eta 0:00:00
#8 12.46 Collecting httpx-sse<1.0.0,>=0.4.0
#8 12.50   Downloading httpx_sse-0.4.3-py3-none-any.whl (9.0 kB)
#8 13.25 Collecting SQLAlchemy<3.0.0,>=1.4.0
#8 13.30   Downloading sqlalchemy-2.0.51-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl (3.2 MB)
#8 13.50      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3.2/3.2 MB 16.5 MB/s eta 0:00:00
#8 14.12 Collecting numpy>=1.26.2
#8 14.15   Downloading numpy-2.0.2-cp39-cp39-manylinux_2_17_aarch64.manylinux2014_aarch64.whl (13.9 MB)
#8 14.61      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 13.9/13.9 MB 26.6 MB/s eta 0:00:00
#8 15.01 Collecting ollama<1.0.0,>=0.5.3
#8 15.03   Downloading ollama-0.6.2-py3-none-any.whl (15 kB)
#8 15.19 Collecting propcache>=0.2.0
#8 15.22   Downloading propcache-0.4.1-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl (201 kB)
#8 15.23      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 201.1/201.1 KB 21.0 MB/s eta 0:00:00
#8 15.27 Collecting aiohappyeyeballs>=2.5.0
#8 15.30   Downloading aiohappyeyeballs-2.6.1-py3-none-any.whl (15 kB)
#8 15.85 Collecting yarl<2.0,>=1.17.0
#8 15.88   Downloading yarl-1.22.0-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl (347 kB)
#8 15.90      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 347.1/347.1 KB 25.1 MB/s eta 0:00:00
#8 16.04 Collecting async-timeout<6.0,>=4.0
#8 16.07   Downloading async_timeout-5.0.1-py3-none-any.whl (6.2 kB)
#8 16.12 Collecting attrs>=17.3.0
#8 16.15   Downloading attrs-26.1.0-py3-none-any.whl (67 kB)
#8 16.15      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 67.5/67.5 KB 17.0 MB/s eta 0:00:00
#8 16.65 Collecting multidict<7.0,>=4.5
#8 16.68   Downloading multidict-6.7.1-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl (240 kB)
#8 16.69      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 240.1/240.1 KB 28.9 MB/s eta 0:00:00
#8 16.73 Collecting aiosignal>=1.4.0
#8 16.75   Downloading aiosignal-1.4.0-py3-none-any.whl (7.5 kB)
#8 16.91 Collecting frozenlist>=1.1.1
#8 16.93   Downloading frozenlist-1.8.0-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl (221 kB)
#8 16.94      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 221.5/221.5 KB 47.0 MB/s eta 0:00:00
#8 16.99 Collecting typing-inspect<1,>=0.4.0
#8 17.10   Downloading typing_inspect-0.9.0-py3-none-any.whl (8.8 kB)
#8 17.19 Collecting marshmallow<4.0.0,>=3.18.0
#8 17.21   Downloading marshmallow-3.26.2-py3-none-any.whl (50 kB)
#8 17.21      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 51.0/51.0 KB 22.7 MB/s eta 0:00:00
#8 17.28 Collecting zipp>=3.20
#8 17.30   Downloading zipp-3.23.1-py3-none-any.whl (10 kB)
#8 17.35 Collecting jsonpointer>=1.9
#8 17.38   Downloading jsonpointer-3.0.0-py2.py3-none-any.whl (7.6 kB)
#8 17.49 Collecting async-timeout<6.0,>=4.0
#8 17.61   Downloading async_timeout-4.0.3-py3-none-any.whl (5.7 kB)
#8 17.66 Collecting langchain-text-splitters<1.0.0,>=0.3.9
#8 17.68   Downloading langchain_text_splitters-0.3.11-py3-none-any.whl (33 kB)
#8 17.74 Collecting requests-toolbelt>=1.0.0
#8 17.77   Downloading requests_toolbelt-1.0.0-py2.py3-none-any.whl (54 kB)
#8 17.77      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 54.5/54.5 KB 25.4 MB/s eta 0:00:00
#8 17.94 Collecting zstandard>=0.23.0
#8 17.96   Downloading zstandard-0.25.0-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.whl (5.1 MB)
#8 18.15      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 5.1/5.1 MB 26.8 MB/s eta 0:00:00
#8 18.71 Collecting orjson>=3.9.14
#8 18.75   Downloading orjson-3.11.5-cp39-cp39-manylinux_2_17_aarch64.manylinux2014_aarch64.whl (132 kB)
#8 18.76      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 132.2/132.2 KB 32.1 MB/s eta 0:00:00
#8 18.83 Collecting httpx<1,>=0.23.0
#8 18.85   Downloading httpx-0.28.1-py3-none-any.whl (73 kB)
#8 18.85      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 73.5/73.5 KB 28.9 MB/s eta 0:00:00
#8 18.93 Collecting typing-inspection>=0.4.2
#8 18.95   Downloading typing_inspection-0.4.2-py3-none-any.whl (14 kB)
#8 20.40 Collecting pydantic-core==2.46.4
#8 20.43   Downloading pydantic_core-2.46.4-cp39-cp39-manylinux_2_17_aarch64.manylinux2014_aarch64.whl (2.0 MB)
#8 20.52      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.0/2.0 MB 24.8 MB/s eta 0:00:00
#8 20.56 Collecting annotated-types>=0.6.0
#8 20.59   Downloading annotated_types-0.7.0-py3-none-any.whl (13 kB)
#8 20.64 Collecting python-dotenv>=0.21.0
#8 20.75   Downloading python_dotenv-1.2.1-py3-none-any.whl (21 kB)
#8 21.07 Collecting charset_normalizer<4,>=2
#8 21.09   Downloading charset_normalizer-3.4.7-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl (200 kB)
#8 21.10      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 200.6/200.6 KB 22.5 MB/s eta 0:00:00
#8 21.16 Collecting certifi>=2017.4.17
#8 21.27   Downloading certifi-2026.6.17-py3-none-any.whl (133 kB)
#8 21.28      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 133.3/133.3 KB 43.1 MB/s eta 0:00:00
#8 21.32 Collecting idna<4,>=2.5
#8 21.34   Downloading idna-3.18-py3-none-any.whl (65 kB)
#8 21.35      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 65.5/65.5 KB 15.0 MB/s eta 0:00:00
#8 21.42 Collecting urllib3<3,>=1.21.1
#8 21.44   Downloading urllib3-2.6.3-py3-none-any.whl (131 kB)
#8 21.45      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 131.6/131.6 KB 24.7 MB/s eta 0:00:00
#8 21.79 Collecting greenlet>=1
#8 21.81   Downloading greenlet-3.2.5-cp39-cp39-manylinux2014_aarch64.manylinux_2_17_aarch64.whl (631 kB)
#8 21.84      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 631.8/631.8 KB 31.2 MB/s eta 0:00:00
#8 21.97 Collecting anyio
#8 21.99   Downloading anyio-4.12.1-py3-none-any.whl (113 kB)
#8 22.00      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 113.6/113.6 KB 26.2 MB/s eta 0:00:00
#8 22.05 Collecting httpcore==1.*
#8 22.07   Downloading httpcore-1.0.9-py3-none-any.whl (78 kB)
#8 22.08      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 78.8/78.8 KB 38.0 MB/s eta 0:00:00
#8 22.12 Collecting h11>=0.16
#8 22.15   Downloading h11-0.16.0-py3-none-any.whl (37 kB)
#8 22.35 Collecting mypy-extensions>=0.3.0
#8 22.37   Downloading mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
#8 22.50 Collecting exceptiongroup>=1.0.2
#8 22.52   Downloading exceptiongroup-1.3.1-py3-none-any.whl (16 kB)
#8 22.79 Installing collected packages: zstandard, zipp, uuid-utils, urllib3, typing-extensions, tenacity, PyYAML, python-dotenv, propcache, packaging, orjson, numpy, mypy-extensions, markupsafe, jsonpointer, itsdangerous, idna, httpx-sse, h11, greenlet, frozenlist, click, charset_normalizer, certifi, blinker, attrs, async-timeout, annotated-types, aiohappyeyeballs, werkzeug, typing-inspection, typing-inspect, SQLAlchemy, requests, pydantic-core, multidict, marshmallow, jsonpatch, jinja2, importlib-metadata, httpcore, exceptiongroup, aiosignal, yarl, requests-toolbelt, pydantic, flask, dataclasses-json, anyio, pydantic-settings, httpx, aiohttp, ollama, langsmith, langchain-core, langchain-text-splitters, langchain-ollama, langchain, langchain-community
#8 29.21 Successfully installed PyYAML-6.0.3 SQLAlchemy-2.0.51 aiohappyeyeballs-2.6.1 aiohttp-3.13.5 aiosignal-1.4.0 annotated-types-0.7.0 anyio-4.12.1 async-timeout-4.0.3 attrs-26.1.0 blinker-1.9.0 certifi-2026.6.17 charset_normalizer-3.4.7 click-8.1.8 dataclasses-json-0.6.7 exceptiongroup-1.3.1 flask-3.1.3 frozenlist-1.8.0 greenlet-3.2.5 h11-0.16.0 httpcore-1.0.9 httpx-0.28.1 httpx-sse-0.4.3 idna-3.18 importlib-metadata-8.7.1 itsdangerous-2.2.0 jinja2-3.1.6 jsonpatch-1.33 jsonpointer-3.0.0 langchain-0.3.30 langchain-community-0.3.31 langchain-core-0.3.86 langchain-ollama-0.3.10 langchain-text-splitters-0.3.11 langsmith-0.4.37 markupsafe-3.0.3 marshmallow-3.26.2 multidict-6.7.1 mypy-extensions-1.1.0 numpy-2.0.2 ollama-0.6.2 orjson-3.11.5 packaging-25.0 propcache-0.4.1 pydantic-2.13.4 pydantic-core-2.46.4 pydantic-settings-2.11.0 python-dotenv-1.2.1 requests-2.32.5 requests-toolbelt-1.0.0 tenacity-9.1.2 typing-extensions-4.15.0 typing-inspect-0.9.0 typing-inspection-0.4.2 urllib3-2.6.3 uuid-utils-0.15.0 werkzeug-3.1.8 yarl-1.22.0 zipp-3.23.1 zstandard-0.25.0
#8 29.21 WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv
#8 29.39 WARNING: You are using pip version 22.0.4; however, version 26.0.1 is available.
#8 29.39 You should consider upgrading via the '/usr/local/bin/python -m pip install --upgrade pip' command.
#8 DONE 30.2s

#9 [4/4] COPY . .
#9 DONE 0.0s

#10 exporting to image
#10 exporting layers
#10 exporting layers 1.0s done
#10 writing image sha256:2b3f7626072aae93e5a3e43bdd5ae730227cffa992e02cce96ab9fea824d0efe done
#10 naming to docker.io/library/llm_monitor-langchain_service done
#10 DONE 1.0s

#11 resolving provenance for metadata file
#11 DONE 0.0s
[+] Building 1/1
 ✔ llm_monitor-langchain_service  Built                                                     0.0s 
 3. Spinning up isolated Langchain and Ollama network stack...
[+] Running 5/5
 ✔ Network llm_monitor_default       Created                                                0.0s 
 ✔ Volume "llm_monitor_ollama_data"  Created                                                0.0s 
 ✔ Container ollama_service          Started                                                0.3s 
 ✔ Container langchain_service       Started                                                0.3s 
 ✔ Container ollama_pull_model       Started                                                0.4s 
  4. Purging dangling or stale images to save MacBook disk space...
Deleted Images:
deleted: sha256:1359aa3e14cf5577b087df07dd6ec914d01ffd3552d7f10c575369ef9268ce52

Total reclaimed space: 0B
 Up and running. View real-time logs with:
docker compose -p llm_monitor logs -f langchain_service
timothygrant > 

Then when I attempt to hit my langchain flask container with a curl command of 

```
curl -X POST http://localhost:5001/test \
     -H "Content-Type: application/json" \
     -d '{"userId": "dev_123", "chatMessage": "Write a haiku about computers."}'
```

I am getting a response of

```
timothygrant > 
timothygrant > curl -X POST http://localhost:5001/test \
     -H "Content-Type: application/json" \
     -d '{"userId": "dev_123", "chatMessage": "Write a haiku about computers."}'
```

and then the system freezes. I have no idea if it is working or not. My computer is really weak (Macbook air M1 chip), so I don't know if it is just that the llm is taking a really long time, or if something is broken in my system. I then go to the docker logs and do this

docker logs -f ollama_pull_model

and I get a response of 

.....
41da8a46ea9255175","total":1482,"completed":1482}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 832dd9e00a68","digest":"sha256:832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e","total":11343,"completed":11343}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"pulling 377ac4d7aeef","digest":"sha256:377ac4d7aeefd5b870c9fccff9a6d4df36901d99fe3277c2f755bc401601ba1c","total":487,"completed":487}
{"status":"verifying sha256 digest"}
{"status":"writing manifest"}
{"status":"success"}
100  74366   0  74342   0     24   2236      0           00:33           1627
timothygrant > 

# Gaps I found in myself while trying to do this section

## Gaps in Docker
- Docker Volumes
- Tear down / build up of docker components without cluttering system
- How the .sh start up build scripts are interacting with the docker containers.
- I was told that I need to wait until docker has fully started up and gotten all of the information it needs before I attempt to invoke things. I was told that I can look at the logs to see this. But I don't understand the underlying concept of what is failing, why it is failing, or how to use the logs to deterimine the state of the system.
- How does Docker Cashe interact with Docker Volumes?
- I am able to start up my system with test_start_up.sh I think it is working, but I realized that I am really struggling to understand what is actually happening. I feel that I am just randomly doing the command, but I don't know how to troubleshoot AT ALL because I don't understand the actual docker system which is being build up right now. 
