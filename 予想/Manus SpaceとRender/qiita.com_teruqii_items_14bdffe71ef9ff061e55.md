# MATLABで競艇の解析を始めよう（競走結果データの読み込み） #ボートレース - Qiita

**URL:** https://qiita.com/teruqii/items/14bdffe71ef9ff061e55

---

search
Login
Signup
Trend
Question
Stock List
Official Event
Official Column
open_in_new
Organization
Qiita Careers
open_in_new
AI x Dev x Team
open_in_new
Qiita Careers powered by IndeedPR

求人サイト「Qiita Careers powered by Indeed」では、エンジニアのあなたにマッチした求人が見つかります。

求人を探す
open_in_new
また後で
11
4
more_horiz
MATLABボートレース解析の３番目です。
とりあえず、ファイルの中身を見てみないとね。
例えばボートレース新聞を作るとして・・
もっとシンプルなプログラムにならんのかね。
というわけで、結果のデータも取り込めました。
info

More than 5 years have passed since last update.

@teruqii
(Terui Takeyoshi)
MATLABで競艇の解析を始めよう（競走結果データの読み込み）
MATLAB
競艇
ボートレース
Last updated at 2019-08-19
Posted at 2019-08-13
MATLABボートレース解析の３番目です。

　昨日の大山千広選手すごかったですよねー、という日に書いております。

　さて、１番目の記事でダウンロードができて、２番目の記事で出走表を読み込めました！
あとはレース結果のファイル（K190801 みたいなやつ）ですね。

とりあえず、ファイルの中身を見てみないとね。

2019/8/1 の競走結果 K190801.TXT はこんな感じ。


STARTK
23KBGN
唐　津［成績］      8/ 1      ヴィーナスシリーズ第  第 4日

                            ＊＊＊　競走成績　＊＊＊

          ヴィーナスシリーズ第７戦ＲＫＢラジオ杯　　　　　　

   第 4日          2019/ 8/ 1                             ボートレース唐　津

               －内容については主催者発行のものと照合して下さい－

   [払戻金]       ３連単           ３連複           ２連単         ２連複
           1R  1-2-4    1400    1-2-4     820    1-2     430    1-2     330
           2R  1-3-2     660    1-2-3     170    1-3     450    1-3     380
           3R  3-2-1    1380    1-2-3     170    3-2     680    2-3     570
           4R  3-5-2    9420    2-3-5    3000    3-5     600    3-5     640
           5R  1-2-5   13880    1-2-5    4860    1-2     800    1-2     730
           6R  6-4-5   28120    4-5-6    4840    6-4    3020    4-6    1300
           7R  2-3-5    9340    2-3-5    2720    2-3    1140    2-3     600
           8R  3-6-2    1080    2-3-6     430    3-6     350    3-6     380
           9R  1-2-3     590    1-2-3     230    1-2     250    1-2     250
          10R  3-4-5   21230    3-4-5    3900    3-4    5370    3-4    2530
          11R  2-1-4    1260    1-2-4     340    2-1     380    1-2     150
          12R  2-1-6   11640    1-2-6    2460    2-1     860    1-2     170



   1R       一　　般　　                 H1800m  晴　  風  北　　 1m  波　  1cm
  着 艇 登番 　選　手　名　　ﾓｰﾀｰ ﾎﾞｰﾄ 展示 進入 ｽﾀｰﾄﾀｲﾐﾝｸ ﾚｰｽﾀｲﾑ 抜き　　　
-------------------------------------------------------------------------------
  01  1 4627 藤　原　　菜　希 63   76  6.72   1    0.09     1.50.0
  02  2 5019 柴　田　　百　恵 17   45  6.71   2    0.06     1.52.0
  03  4 4947 間　庭　　菜　摘 18   72  6.76   4    0.03     1.53.3
  04  5 4994 山　本　　梨　菜 25   65  6.75   5    0.04     1.53.8
  05  3 4758 富　樫　　麗　加 65   35  6.76   3    0.08     1.53.9
  06  6 5057 上　田　　紗　奈 33   55  6.69   6    0.15     1.55.2

        単勝     1          100  
        複勝     1          100  2          110  
        ２連単   1-2        430  人気     2 
        ２連複   1-2        330  人気     2 
        拡連複   1-2        180  人気     2 
                 1-4        240  人気     3 
                 2-4        760  人気     9 
        ３連単   1-2-4     1400  人気     5 
        ３連複   1-2-4      820  人気     4 


   2R       一　　般　　                 H1800m  晴　  風  北　　 2m  波　  2cm
  着 艇 登番 　選　手　名　　ﾓｰﾀｰ ﾎﾞｰﾄ 展示 進入 ｽﾀｰﾄﾀｲﾐﾝｸ ﾚｰｽﾀｲﾑ 逃げ　　　
-------------------------------------------------------------------------------
  01  1 4885 大　山　　千　広 26   66  6.78   1    0.10     1.49.2
  02  3 4938 小　芦　　るり華 23   34  6.70   3    0.13     1.51.9
  03  2 4556 竹　井　　奈　美 46   75  6.75   2    0.15     1.52.8
  04  4 4923 末　武　　里奈子 16   50  6.78   4    0.14     1.54.9
  05  6 5013 山　下　　夏　鈴 53   79  6.78   6    0.18     1.56.4
  06  5 4997 濱　崎　　寿里矢 11   47  6.82   5    0.16     1.57.9

        単勝     1          110  
        複勝     1          120  3          190  
        ２連単   1-3        450  人気     2 
        ２連複   1-3        380  人気     2 
        拡連複   1-3        140  人気     2 
                 1-2        100  人気     1 
                 2-3        160  人気     4 
        ３連単   1-3-2      660  人気     3 
        ３連複   1-2-3      170  人気     1 

--- まだまだ続く ---



という感じ。（1R の予想が外れてる・・・）
まずは何をデータとして取ろうかなー、っていうのを考えないとダメですね。

例えばボートレース新聞を作るとして・・

　新聞を作る人たちは、オッズを見る前に予想しなきゃいけない（そして印刷して販売しなきゃいけない）ので、オッズとか配当以外を取り込んで選手毎に分けてしまいましょう。

%% レース結果の読み込み
addpath('C:\work\boat')
ix = datenum('20190801','YYYYmmDD');
fname = ['K',datestr(ix,'YYmmDD'),'.TXT'];
fid = fopen(fname);
S = textscan(fid,'%s','delimiter','\n');
C = S{1};
fclose(fid);
T_Result = table;

%% BGN/ENDを探す
KBGN = find(contains(C,'BGN'));
KEND = find(contains(C,'END'));

%% BGN-END Loop
for BEloop = 1:length(KBGN)
    
    %% BGN-ENDで切り取る
    res = C(KBGN(BEloop)+1:KEND(BEloop)-1);
    res(cellfun(@isempty,res)) = [];
    
    % 場所
    place = res{1}(1:3);
    place(place == 12288) = [];
    
    % 開催日と今何日目
    ymd = datestr(ix,'YYYYmmDD');
    idx = regexp(res{1},'第 \w日','match');
    if ~isempty(idx)     % 2018/01/16 の 2525行目にダメデータがあるのでスキップ
        day = str2double(idx{1}(end-1));
        
        start_idx = startsWith(res,'着');
        x = find(start_idx)-1;
        end_x = [x(2:end)-1;length(res)];
        n = length(x);
        
        % ここからレースのループ
        for Rloop = 1:n
            % レース番号
            race = res(x(Rloop):end_x(Rloop));
            oddsidx = find(contains(race,'単勝'));
            if ~isempty(oddsidx)
                race_detail = race(1:oddsidx-1);
                odds_detail = race(oddsidx:end);
                txt = textscan(race_detail{1},'%s');
                R = txt{1}{1};  % レース番号
                R = str2double(R(1:end-1));
                R_NAME = txt{1}{2};   % レース名
                R_NAME(R_NAME == 12288) = [];
                
                midx = find(~cellfun(@isempty,regexp(txt{1},'H\d+m')));
                LENGTH = txt{1}{midx};
                LENGTH = str2double(LENGTH(2:end-1));    % H1800m の H/m を捨てる
                WEATHER = txt{1}{midx+1};
                WEATHER(WEATHER == 12288) = [];
                midx = find(~cellfun(@isempty,regexp(txt{1},'風')));
                WINDDIR = txt{1}{midx+1};
                WINDDIR(WINDDIR == 12288) = [];
                WINDPOW = txt{1}{midx+2};
                WINDPOW(WINDPOW == 12288) = [];
                WINDPOW(end) = [];
                WINDPOW = str2double(WINDPOW);
                midx = find(~cellfun(@isempty,regexp(txt{1},'波')));
                WAVE = txt{1}{midx+1};
                WAVE(WAVE == 12288) = [];
                WAVE(end-1:end) = [];
                WAVE = str2double(WAVE);
                
                % 着順
                FIN_idx = find(~cellfun(@isempty,regexp(race_detail,'^0\d')));
                for iy = 1:length(FIN_idx)
                    rc = textscan(race_detail{FIN_idx(iy)},'%s');
                    FRAME = str2double(rc{1}{2});    % 枠番
                    NAME = str2double(rc{1}{3});    % 選手番号
                    MOTOR = str2double(rc{1}{5});    % モーター番号
                    BOAT = str2double(rc{1}{6});    % ボート番号
                    EXTIME = str2double(rc{1}{7});   % 展示タイム
                    ENTRY = str2double(rc{1}{8});   % 進入コース（本番）
                    FINISH = str2double(rc{1}{1});   % 結果
                    T_Result(end+1,:) = {place,ymd,day,R,R_NAME,LENGTH,WEATHER,WINDDIR,WINDPOW,WAVE,FRAME,NAME,MOTOR,BOAT,EXTIME,ENTRY,FINISH};
                end
            end
        end
    end
end
T_Result.Properties.VariableNames = {'Place','YYYYMMDD','Day','R','RaceName','Distance','Weather','WindDir','WindPow','Wave','Frame','NameNo','Motor','Boat','ExtTime','Entry','Finish'};


取れたかね。
コマンドウィンドウでチェックしてみよう。

>> T_Result

T_Result =

  926×17 table

     Place      YYYYMMDD     Day    R       RaceName      Distance    Weather    WindDir    WindPow    Wave    Frame    NameNo    Motor    Boat    ExtTime    Entry    Finish
    _______    __________    ___    __    ____________    ________    _______    _______    _______    ____    _____    ______    _____    ____    _______    _____    ______

    '唐津'     '20190801'     4      1    '一般'             1800      '晴'       '北'           1         1       1       4627      63       76      6.72        1        1   
    '唐津'     '20190801'     4      1    '一般'             1800      '晴'       '北'           1         1       2       5019      17       45      6.71        2        2   
    '唐津'     '20190801'     4      1    '一般'             1800      '晴'       '北'           1         1       4       4947      18       72      6.76        4        3   
    '唐津'     '20190801'     4      1    '一般'             1800      '晴'       '北'           1         1       5       4994      25       65      6.75        5        4   
    '唐津'     '20190801'     4      1    '一般'             1800      '晴'       '北'           1         1       3       4758      65       35      6.76        3        5   
    '唐津'     '20190801'     4      1    '一般'             1800      '晴'       '北'           1         1       6       5057      33       55      6.69        6        6   
    '唐津'     '20190801'     4      2    '一般'             1800      '晴'       '北'           2         2       1       4885      26       66      6.78        1        1   
    '唐津'     '20190801'     4      2    '一般'             1800      '晴'       '北'           2         2       3       4938      23       34       6.7        3        2   
    '唐津'     '20190801'     4      2    '一般'             1800      '晴'       '北'           2         2       2       4556      46       75      6.75        2        3   
    '唐津'     '20190801'     4      2    '一般'             1800      '晴'       '北'           2         2       4       4923      16       50      6.78        4        4   
    '唐津'     '20190801'     4      2    '一般'             1800      '晴'       '北'           2         2       6       5013      53       79      6.78        6        5   
    '唐津'     '20190801'     4      2    '一般'             1800      '晴'       '北'           2         2       5       4997      11       47      6.82        5        6   
...
...


いい感じ！926人分の結果ですね。
テーブルの最後の Finish が着順なので、これを予想できればいいね。

もっとシンプルなプログラムにならんのかね。

　出走表はフォーマットも決まってて取りやすいんですけど、結果は、例えば転覆があったり失格があったり、そもそも 8R 以降が台風で中止とか、江戸川の波が高すぎて中止とか、レース数とか結果フォーマットもまちまちになるので、こんな感じのIF文だらけになります。
（あと、意外に誤字脱字とか編集ミスっぽいファイルも時々ある。）

というわけで、結果のデータも取り込めました。

　あとは着順の予想をするためには、テーブルの操作とかデータをまとめたりしないといけないんですけど、とりあえずここまで。
　続きが知りたい人は「いいね」で教えてね。（いいね依存症）

→　４番目の記事 を書いたよ。

11
4
comment
0

Register as a new user and use Qiita more conveniently

You get articles that match your needs
You can efficiently read back useful information
You can use dark theme
What you can do with signing up
Sign up
Login
Comments
No comments

Let's comment your feelings that are more than good

Login
Sign Up

How developers code is here.

© 2011-2026Qiita Inc.

Guide & Help

About
Terms
Privacy
Guideline
Media Kit
Feedback/Requests
Help
Advertisement

Contents

Release Note
Official Event
Official Column
Advent Calendar
Qiita Tech Festa
Qiita Award
Engineer White Paper
API

Official Accounts

@Qiita
@qiita_milestone
@qiitapoi
Facebook
YouTube
Podcast

Our service

Qiita Team
Qiita Zine
Official Shop

Company

About Us
Careers
Qiita Blog
News Release