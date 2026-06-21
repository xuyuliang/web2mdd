##  第一次安装
先pip安装

pip install morphoneme

第一次使用：
先下载这个
https://github.com/connoryang331/morphoneme/releases/download/v0.1.0/morphoneme.db.zip

也可以直接尝试使用，程序会提醒你去下载或者自动帮你下载

.\venv\Scripts\mp search *ough     

第一次，它会说：
Database not found locally. Downloading from https://github.com/connoryang331/morphoneme/releases/download/v0.1.0/morphoneme.db.zip...

你需要安装到 C:\Users\你的用户名\.morphoneme\morphoneme.db.

如果在命令行运行

.\venv\Scripts\mp search *ough     
得到这样的结果，就算安装完成了。

Found 139 results (source=both, seg=both):
  aldbrough                       umlabeller=aldbrough                            citylex=                                          fq=0.03  pron=L AA1 D B R UW2
  although                        umlabeller=                                     citylex={al--though}                              fq=16.08  pron=AO2 L DH OW1
  ......

## 使用
