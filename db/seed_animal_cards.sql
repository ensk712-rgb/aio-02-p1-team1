-- 동물 정보카드(animal_cards) mock 데이터 적재 스크립트
-- data/animal_cards/*.json 100건을 그대로 옮긴 것입니다.
-- 실행: psql "$DATABASE_URL" -f db/seed_animal_cards.sql
BEGIN;
-- pgvector 확장 (지금은 embedding 컬럼을 쓰지 않지만, 이후 추가할 때를 대비해 미리 켜둡니다)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS animal_cards (
    id SERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    collection TEXT NOT NULL,
    page INTEGER,
    text TEXT NOT NULL,
    keywords TEXT [] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_animal_cards_collection ON animal_cards (collection);
-- 재실행해도 안전하도록 doc_id 충돌 시 내용을 덮어씁니다 (upsert).
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-ALLIGATOR',
        '악어',
        'animal_cards',
        1,
        '악어는 악어관에서 지내는 파충류입니다. 고기와 물고기 위주의 먹이를 며칠에 한 번 먹습니다. 물속에서 눈과 코만 내놓고 숨어있는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['악어', '악어관', '파충류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-ALPACA',
        '알파카',
        'animal_cards',
        1,
        '알파카는 알파카관에서 지내는 초식동물입니다. 건초와 목초 위주의 먹이를 하루 두 번 먹습니다. 부드러운 털을 가지고 있어 관람객에게 인기가 많습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['알파카', '알파카관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-BABOON',
        '개코원숭이',
        'animal_cards',
        1,
        '개코원숭이는 개코원숭이관에서 지내는 잡식동물입니다. 과일과 채소를 섞은 먹이를 하루 두 번 먹습니다. 무리를 지어 생활하며 서열 관계가 뚜렷합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['개코원숭이', '개코원숭이관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-BEAR',
        '곰',
        'animal_cards',
        1,
        '곰은 곰관에서 지내는 잡식동물입니다. 과일과 고기를 섞은 먹이를 하루 두 번 먹습니다. 겨울잠을 자는 습성이 있어 계절에 따라 활동량이 달라집니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['곰', '곰관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-BEAVER',
        '비버',
        'animal_cards',
        1,
        '비버는 비버관에서 지내는 초식동물입니다. 나뭇가지와 채소 위주의 먹이를 하루 두 번 먹습니다. 나뭇가지를 모아 댐을 만드는 습성으로 잘 알려져 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['비버', '비버관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-BOA',
        '보아뱀',
        'animal_cards',
        1,
        '보아뱀은 보아뱀관에서 지내는 파충류입니다. 며칠에 한 번 통째 먹이를 먹습니다. 먹이를 몸으로 조여서 사냥하는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['보아뱀', '보아뱀관', '파충류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-BOAR',
        '멧돼지',
        'animal_cards',
        1,
        '멧돼지는 멧돼지관에서 지내는 잡식동물입니다. 채소와 곡물을 섞은 먹이를 하루 두 번 먹습니다. 땅을 코로 파헤치며 먹이를 찾는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['멧돼지', '멧돼지관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-BULLFROG',
        '황소개구리',
        'animal_cards',
        1,
        '황소개구리는 황소개구리관에서 지내는 양서류입니다. 작은 곤충과 물고기를 섞은 먹이를 하루 한 번 먹습니다. 낮게 울리는 큰 울음소리로 잘 알려져 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['황소개구리', '황소개구리관', '양서류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-BUTTERFLY',
        '나비',
        'animal_cards',
        1,
        '나비는 나비관에서 지내는 곤충입니다. 꽃꿀 위주의 먹이를 하루 여러 번 나누어 먹습니다. 온실 안을 자유롭게 날아다니는 모습을 관찰할 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['나비', '나비관', '곤충']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-CAMEL',
        '낙타',
        'animal_cards',
        1,
        '낙타는 낙타관에서 지내는 초식동물입니다. 건초 위주의 먹이를 하루 두 번 먹습니다. 등의 혹에 지방을 저장해 물 없이도 오래 버틸 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['낙타', '낙타관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-CHAMELEON',
        '카멜레온',
        'animal_cards',
        1,
        '카멜레온은 카멜레온관에서 지내는 파충류입니다. 곤충 위주의 먹이를 하루 한 번 먹습니다. 몸의 색을 주변 환경에 맞춰 바꾸는 것으로 유명합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['카멜레온', '카멜레온관', '파충류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-CHEETAH',
        '치타',
        'animal_cards',
        1,
        '치타는 치타관에서 지내는 육식동물입니다. 고기 위주의 먹이를 정해진 시간에 먹습니다. 짧은 시간에 빠르게 달리는 습성이 있어 넓은 방사장에서 지냅니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['치타', '치타관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-CHIMPANZEE',
        '침팬지',
        'animal_cards',
        1,
        '침팬지는 침팬지관에서 지내는 잡식동물입니다. 과일과 채소 위주의 먹이를 하루 여러 번 나누어 먹습니다. 도구를 사용할 줄 아는 지능이 높은 동물로 알려져 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['침팬지', '침팬지관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-CHINCHILLA',
        '친칠라',
        'animal_cards',
        1,
        '친칠라는 친칠라관에서 지내는 초식동물입니다. 건초 위주의 먹이를 하루 두 번 먹습니다. 부드러운 털을 가지고 있으며 모래 목욕을 즐깁니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['친칠라', '친칠라관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-CLOWNFISH',
        '흰동가리',
        'animal_cards',
        1,
        '흰동가리는 흰동가리관에서 지내는 어류입니다. 작은 플랑크톤과 사료를 하루 두 번 먹습니다. 말미잘과 함께 지내는 공생 관계로 잘 알려져 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['흰동가리', '흰동가리관', '해양', '수족관']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-COCKATOO',
        '왕관앵무',
        'animal_cards',
        1,
        '왕관앵무는 왕관앵무관에서 지내는 조류입니다. 곡물과 과일을 섞은 먹이를 하루 두 번 먹습니다. 머리 위 볏 깃털을 세우는 모습이 특징입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['왕관앵무', '왕관앵무관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-COYOTE',
        '코요테',
        'animal_cards',
        1,
        '코요테는 코요테관에서 지내는 육식동물입니다. 고기 위주의 먹이를 하루 한 번 먹습니다. 해질 무렵 활동이 활발해지는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['코요테', '코요테관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-CRANE',
        '두루미',
        'animal_cards',
        1,
        '두루미는 두루미관에서 지내는 조류입니다. 물고기와 곡물을 섞은 먹이를 하루 두 번 먹습니다. 긴 다리와 목을 가지고 있으며 우아한 걸음걸이가 특징입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['두루미', '두루미관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-DEER',
        '사슴',
        'animal_cards',
        1,
        '사슴은 사슴관에서 지내는 초식동물입니다. 건초와 채소 위주의 먹이를 하루 두 번 먹습니다. 무리를 지어 방사장을 돌아다니는 모습을 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['사슴', '사슴관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-DOLPHIN',
        '돌고래',
        'animal_cards',
        1,
        '돌고래는 돌고래관에서 지내는 어류입니다. 물고기 위주의 먹이를 하루 여러 번 나누어 먹습니다. 높은 지능을 가지고 있으며 무리를 지어 생활합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['돌고래', '돌고래관', '해양', '수족관']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-EAGLE',
        '독수리',
        'animal_cards',
        1,
        '독수리는 독수리관에서 지내는 조류입니다. 고기 위주의 먹이를 하루 한 번 공급받습니다. 날카로운 부리와 발톱을 가진 맹금류입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['독수리', '독수리관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-ELEPHANT',
        '코끼리',
        'animal_cards',
        1,
        '코끼리는 코끼리관 실내 사육장에서 지내는 초식동물입니다. 나뭇잎과 채소, 건초를 주로 먹으며 몸집이 커서 하루에 많은 양의 먹이가 필요합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['코끼리', '코끼리관', '초식', '건초', '채소', '먹이']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-EMU',
        '에뮤',
        'animal_cards',
        1,
        '에뮤는 에뮤관에서 지내는 조류입니다. 곡물과 채소를 섞은 먹이를 하루 두 번 먹습니다. 타조와 비슷하게 생겼지만 몸집이 조금 더 작습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['에뮤', '에뮤관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-FALLOWDEER',
        '다마사슴',
        'animal_cards',
        1,
        '다마사슴은 다마사슴관에서 지내는 초식동물입니다. 건초와 채소 위주의 먹이를 하루 두 번 먹습니다. 무늬가 있는 털을 가지고 있으며 무리 생활을 합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['다마사슴', '다마사슴관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-FLAMINGO',
        '플라밍고',
        'animal_cards',
        1,
        '플라밍고는 플라밍고관에서 지내는 조류입니다. 새우와 조류를 섞은 먹이를 하루 두 번 먹습니다. 한쪽 다리로 서서 쉬는 모습이 대표적인 관람 포인트입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['플라밍고', '플라밍고관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-FOX',
        '여우',
        'animal_cards',
        1,
        '여우는 여우관에서 지내는 육식동물입니다. 고기와 채소를 섞은 먹이를 하루 한 번 먹습니다. 야행성에 가까워 이른 아침이나 늦은 오후에 활동하는 모습을 자주 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['여우', '여우관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-GALAPAGOSTORTOISE',
        '갈라파고스땅거북',
        'animal_cards',
        1,
        '갈라파고스땅거북은 갈라파고스땅거북관에서 지내는 파충류입니다. 채소와 건초 위주의 먹이를 하루 한 번 먹습니다. 매우 오래 사는 것으로 알려진 대형 육지거북입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['갈라파고스땅거북', '갈라파고스땅거북관', '파충류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-GAZELLE',
        '가젤',
        'animal_cards',
        1,
        '가젤은 가젤관에서 지내는 초식동물입니다. 건초와 풀 위주의 먹이를 하루 두 번 먹습니다. 무리를 지어 다니며 빠른 순발력을 가지고 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['가젤', '가젤관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-GECKO',
        '도마뱀붙이',
        'animal_cards',
        1,
        '도마뱀붙이는 도마뱀붙이관에서 지내는 파충류입니다. 곤충 위주의 먹이를 하루 한 번 먹습니다. 벽이나 유리를 자유롭게 기어오를 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['도마뱀붙이', '도마뱀붙이관', '파충류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-GIRAFFE',
        '기린',
        'animal_cards',
        1,
        '기린은 기린관 야외 방사장에서 지내는 초식동물로, 목이 길어 높은 나뭇잎을 먹는 모습이 특징입니다. 나뭇잎과 건초를 주로 먹습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['기린', '기린관', '초식', '나뭇잎', '건초', '먹이']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-GOAT',
        '산양',
        'animal_cards',
        1,
        '산양은 산양관에서 지내는 초식동물입니다. 건초와 채소 위주의 먹이를 하루 두 번 먹습니다. 바위가 많은 지형을 오르내리는 것을 좋아합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['산양', '산양관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-GORILLA',
        '고릴라',
        'animal_cards',
        1,
        '고릴라는 고릴라관에서 지내는 잡식동물입니다. 채소와 과일 위주의 먹이를 하루 여러 번 나누어 먹습니다. 무리를 이루어 생활하며 낮 시간 대부분을 휴식하며 보냅니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['고릴라', '고릴라관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-HARBORSEAL',
        '물범',
        'animal_cards',
        1,
        '물범은 물범관에서 지내는 어류입니다. 물고기 위주의 먹이를 하루 두 번 먹습니다. 물속에서 재빠르게 헤엄치다가 뭍에 올라와 쉬기도 합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['물범', '물범관', '해양', '수족관']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-HAWK',
        '매',
        'animal_cards',
        1,
        '매는 매관에서 지내는 조류입니다. 고기 위주의 먹이를 하루 한 번 공급받습니다. 매우 빠른 비행 속도를 가진 맹금류로 알려져 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['매', '매관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-HEDGEHOG',
        '고슴도치',
        'animal_cards',
        1,
        '고슴도치는 고슴도치관에서 지내는 잡식동물입니다. 곤충과 채소를 섞은 먹이를 하루 한 번 먹습니다. 위협을 느끼면 몸을 둥글게 말아 가시를 세우는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['고슴도치', '고슴도치관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-HIPPO',
        '하마',
        'animal_cards',
        1,
        '하마는 하마관에서 지내는 초식동물입니다. 건초와 채소 위주의 먹이를 하루 두 번 먹습니다. 낮에는 물속에서 지내다가 저녁에 물 밖으로 나와 먹이를 먹습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['하마', '하마관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-HYENA',
        '하이에나',
        'animal_cards',
        1,
        '하이에나는 하이에나관에서 지내는 육식동물입니다. 고기 위주의 먹이를 하루 한 번 먹습니다. 무리 생활을 하며 큰 울음소리를 내는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['하이에나', '하이에나관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-IGUANA',
        '이구아나',
        'animal_cards',
        1,
        '이구아나는 이구아나관에서 지내는 파충류입니다. 채소와 과일 위주의 먹이를 하루 한 번 먹습니다. 따뜻한 곳에서 몸을 데우는 일광욕을 즐깁니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['이구아나', '이구아나관', '파충류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-IMPALA',
        '임팔라',
        'animal_cards',
        1,
        '임팔라는 임팔라관에서 지내는 초식동물입니다. 건초와 풀 위주의 먹이를 하루 두 번 먹습니다. 높이 뛰어오르는 도약력이 뛰어난 것으로 알려져 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['임팔라', '임팔라관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-JAGUAR',
        '재규어',
        'animal_cards',
        1,
        '재규어는 재규어관에서 지내는 육식동물입니다. 하루 한 번 고기 위주의 먹이를 먹습니다. 물을 좋아해 방사장 안 물웅덩이에서 시간을 보내는 모습을 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['재규어', '재규어관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-JAPANESEMACAQUE',
        '일본원숭이',
        'animal_cards',
        1,
        '일본원숭이는 일본원숭이관에서 지내는 잡식동물입니다. 과일과 곡물을 섞은 먹이를 하루 두 번 먹습니다. 겨울철 온천을 즐기는 습성으로 잘 알려져 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['일본원숭이', '일본원숭이관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-JELLYFISH',
        '해파리',
        'animal_cards',
        1,
        '해파리는 해파리관에서 지내는 어류입니다. 플랑크톤 위주의 먹이를 하루 한 번 공급받습니다. 몸을 규칙적으로 수축시키며 물속을 떠다닙니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['해파리', '해파리관', '해양', '수족관']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-KANGAROO',
        '캥거루',
        'animal_cards',
        1,
        '캥거루는 캥거루관에서 지내는 초식동물입니다. 건초와 채소 위주의 먹이를 하루 두 번 먹습니다. 뒷다리로 껑충 뛰어 이동하는 모습이 특징입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['캥거루', '캥거루관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-KOALA',
        '코알라',
        'animal_cards',
        1,
        '코알라는 코알라관에서 지내는 초식동물입니다. 유칼립투스 잎을 하루 여러 번 나누어 먹습니다. 하루 대부분을 나무 위에서 잠을 자며 보냅니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['코알라', '코알라관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-KOMODODRAGON',
        '코모도왕도마뱀',
        'animal_cards',
        1,
        '코모도왕도마뱀은 코모도왕도마뱀관에서 지내는 파충류입니다. 고기 위주의 먹이를 며칠에 한 번 먹습니다. 세계에서 가장 큰 도마뱀 중 하나로 알려져 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['코모도왕도마뱀', '코모도왕도마뱀관', '파충류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-LEMUR',
        '여우원숭이',
        'animal_cards',
        1,
        '여우원숭이는 여우원숭이관에서 지내는 잡식동물입니다. 과일과 채소를 섞은 먹이를 하루 두 번 먹습니다. 긴 꼬리로 균형을 잡으며 무리를 지어 생활합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['여우원숭이', '여우원숭이관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-LEOPARD',
        '표범',
        'animal_cards',
        1,
        '표범은 표범관에서 지내는 육식동물입니다. 고기 위주의 먹이를 하루 한 번 공급받습니다. 나무 위에 올라가 쉬는 습성이 있어 방사장 곳곳에 오르는 구조물이 설치되어 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['표범', '표범관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-LION',
        '사자',
        'animal_cards',
        1,
        '사자는 사자관에서 지내는 육식동물입니다. 하루 한 번 정해진 시간에 고기 위주의 먹이를 먹습니다. 무리를 지어 생활하며 낮에는 그늘에서 휴식을 취하는 모습을 자주 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['사자', '사자관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-LLAMA',
        '라마',
        'animal_cards',
        1,
        '라마는 라마관에서 지내는 초식동물입니다. 건초와 목초 위주의 먹이를 하루 두 번 먹습니다. 온순한 편이지만 위협을 느끼면 침을 뱉는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['라마', '라마관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-LYNX',
        '스라소니',
        'animal_cards',
        1,
        '스라소니는 스라소니관에서 지내는 육식동물입니다. 고기 위주의 먹이를 하루 한 번 공급받습니다. 귀 끝의 털이 특징이며 은신처에 숨어 지내는 시간이 많습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['스라소니', '스라소니관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-MANTIS',
        '사마귀',
        'animal_cards',
        1,
        '사마귀는 사마귀관에서 지내는 곤충입니다. 작은 곤충을 먹이로 하루 한 번 공급받습니다. 앞다리를 접고 기다리다가 먹이를 낚아채는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['사마귀', '사마귀관', '곤충']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-MARMOSET',
        '마모셋',
        'animal_cards',
        1,
        '마모셋은 마모셋관에서 지내는 잡식동물입니다. 과일과 곤충을 섞은 먹이를 하루 여러 번 나누어 먹습니다. 몸집이 매우 작은 원숭이로 나무 위에서 주로 생활합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['마모셋', '마모셋관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-MEERKAT',
        '미어캣',
        'animal_cards',
        1,
        '미어캣은 미어캣관에서 지내는 육식동물입니다. 곤충과 작은 먹이를 하루 여러 번 나누어 먹습니다. 무리 중 한 마리가 서서 주변을 살피는 보초 행동으로 유명합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['미어캣', '미어캣관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-MOONBEAR',
        '반달가슴곰',
        'animal_cards',
        1,
        '반달가슴곰은 반달가슴곰관에서 지내는 잡식동물입니다. 과일과 고기를 섞은 먹이를 하루 두 번 먹습니다. 가슴에 반달 모양의 흰 무늬가 있는 것이 특징입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['반달가슴곰', '반달가슴곰관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-OKAPI',
        '오카피',
        'animal_cards',
        1,
        '오카피는 오카피관에서 지내는 초식동물입니다. 나뭇잎과 건초 위주의 먹이를 하루 두 번 먹습니다. 기린과 친척 관계이며 다리에 줄무늬가 있는 것이 특징입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['오카피', '오카피관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-ORANGUTAN',
        '오랑우탄',
        'animal_cards',
        1,
        '오랑우탄은 오랑우탄관에서 지내는 잡식동물입니다. 과일 위주의 먹이를 하루 여러 번 나누어 먹습니다. 나무 사이를 팔로 이동하는 모습을 자주 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['오랑우탄', '오랑우탄관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-OSTRICH',
        '타조',
        'animal_cards',
        1,
        '타조는 타조관에서 지내는 조류입니다. 곡물과 채소를 섞은 먹이를 하루 두 번 먹습니다. 날지 못하는 대신 빠르게 달릴 수 있는 다리를 가지고 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['타조', '타조관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-OTTER',
        '수달',
        'animal_cards',
        1,
        '수달은 수달관에서 지내는 육식동물입니다. 물고기 위주의 먹이를 하루 두 번 먹습니다. 물속에서 헤엄치고 노는 모습을 자주 볼 수 있는 인기 관람 동물입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['수달', '수달관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-OWL',
        '부엉이',
        'animal_cards',
        1,
        '부엉이는 부엉이관에서 지내는 조류입니다. 작은 먹이를 하루 한 번 공급받습니다. 야행성이라 낮에는 눈을 감고 쉬는 모습을 자주 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['부엉이', '부엉이관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-PANDA',
        '판다',
        'animal_cards',
        1,
        '판다는 판다관에서 지내는 잡식동물입니다. 대나무를 하루 여러 차례 나누어 먹습니다. 느긋하게 앉아 대나무를 먹는 모습이 대표적인 관람 포인트입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['판다', '판다관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-PARROT',
        '앵무새',
        'animal_cards',
        1,
        '앵무새는 앵무새관에서 지내는 조류입니다. 곡물과 과일을 섞은 먹이를 하루 두 번 먹습니다. 사람의 말소리를 흉내 내는 것으로 잘 알려져 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['앵무새', '앵무새관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-PEACOCK',
        '공작',
        'animal_cards',
        1,
        '공작은 공작관에서 지내는 조류입니다. 곡물과 채소를 섞은 먹이를 하루 두 번 먹습니다. 화려한 꼬리깃을 펼치는 구애 행동으로 유명합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['공작', '공작관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-PELICAN',
        '펠리컨',
        'animal_cards',
        1,
        '펠리컨은 펠리컨관에서 지내는 조류입니다. 물고기 위주의 먹이를 하루 두 번 먹습니다. 큰 부리 아래 주머니로 물고기를 잡는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['펠리컨', '펠리컨관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-PENGUIN',
        '펭귄',
        'animal_cards',
        1,
        '펭귄은 해양관 2층 관람대에서 관찰할 수 있는 바닷새입니다. 물고기를 주식으로 먹으며, 정해진 먹이시간에 사육사가 직접 먹이를 주는 모습을 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['펭귄', '해양관', '물고기', '먹이', '관람대']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-POLARBEAR',
        '북극곰',
        'animal_cards',
        1,
        '북극곰은 북극곰관에서 지내는 육식동물입니다. 생선과 고기 위주의 먹이를 하루 한 번 먹습니다. 물놀이를 즐기며 수조 안에서 헤엄치는 모습을 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['북극곰', '북극곰관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-PRAIRIEDOG',
        '프레리도그',
        'animal_cards',
        1,
        '프레리도그는 프레리도그관에서 지내는 초식동물입니다. 건초와 채소 위주의 먹이를 하루 두 번 먹습니다. 땅굴을 파고 그 안에서 무리 생활을 합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['프레리도그', '프레리도그관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-PYTHONSNAKE',
        '비단뱀',
        'animal_cards',
        1,
        '비단뱀은 비단뱀관에서 지내는 파충류입니다. 며칠에 한 번 통째 먹이를 먹습니다. 몸을 나뭇가지에 감고 쉬는 모습을 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['비단뱀', '비단뱀관', '파충류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-RACCOON',
        '너구리',
        'animal_cards',
        1,
        '너구리는 너구리관에서 지내는 잡식동물입니다. 과일과 채소를 섞은 먹이를 하루 두 번 먹습니다. 야행성에 가까워 저녁 무렵 활동이 활발해집니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['너구리', '너구리관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-REDEAREDSLIDER',
        '붉은귀거북',
        'animal_cards',
        1,
        '붉은귀거북은 붉은귀거북관에서 지내는 파충류입니다. 수생식물과 작은 먹이를 하루 한 번 먹습니다. 물과 육지를 오가며 지내는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['붉은귀거북', '붉은귀거북관', '파충류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-REDPANDA',
        '레서판다',
        'animal_cards',
        1,
        '레서판다는 레서판다관에서 지내는 잡식동물입니다. 대나무와 과일을 하루 여러 번 나누어 먹습니다. 나무 위에서 쉬는 시간이 많고 꼬리로 균형을 잡습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['레서판다', '레서판다관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-REINDEER',
        '순록',
        'animal_cards',
        1,
        '순록은 순록관에서 지내는 초식동물입니다. 건초와 이끼류 위주의 먹이를 하루 두 번 먹습니다. 추운 환경을 좋아해 그늘진 곳에서 쉬는 모습을 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['순록', '순록관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-RHINO',
        '코뿔소',
        'animal_cards',
        1,
        '코뿔소는 코뿔소관에서 지내는 초식동물입니다. 건초와 채소 위주의 먹이를 하루 두 번 먹습니다. 진흙 목욕을 즐기며 방사장 안 웅덩이에서 시간을 보냅니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['코뿔소', '코뿔소관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-RHINOCEROSBEETLE',
        '장수풍뎅이',
        'animal_cards',
        1,
        '장수풍뎅이는 장수풍뎅이관에서 지내는 곤충입니다. 젤리 형태의 먹이를 하루 한 번 먹습니다. 수컷의 큰 뿔이 특징이며 나무 수액을 좋아합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['장수풍뎅이', '장수풍뎅이관', '곤충']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-ROEDEER',
        '노루',
        'animal_cards',
        1,
        '노루는 노루관에서 지내는 초식동물입니다. 건초와 나뭇잎 위주의 먹이를 하루 두 번 먹습니다. 경계심이 많아 소리에 민감하게 반응하는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['노루', '노루관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SALAMANDER',
        '도롱뇽',
        'animal_cards',
        1,
        '도롱뇽은 도롱뇽관에서 지내는 양서류입니다. 작은 곤충을 하루 한 번 먹습니다. 축축한 환경을 좋아하며 야행성에 가깝습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['도롱뇽', '도롱뇽관', '양서류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SCORPION',
        '전갈',
        'animal_cards',
        1,
        '전갈은 전갈관에서 지내는 곤충입니다. 작은 곤충을 며칠에 한 번 먹습니다. 꼬리 끝의 독침으로 먹이를 사냥하는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['전갈', '전갈관', '곤충']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SEALION',
        '바다사자',
        'animal_cards',
        1,
        '바다사자는 바다사자관에서 지내는 어류입니다. 물고기 위주의 먹이를 하루 두 번 먹습니다. 지느러미 발로 뭍을 걸어 다닐 수 있는 것이 특징입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['바다사자', '바다사자관', '해양', '수족관']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SEAOTTER',
        '해달',
        'animal_cards',
        1,
        '해달은 해달관에서 지내는 어류입니다. 조개류와 물고기를 섞은 먹이를 하루 여러 번 나누어 먹습니다. 배 위에 돌을 올려놓고 조개를 깨 먹는 습성으로 유명합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['해달', '해달관', '해양', '수족관']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SEATURTLE',
        '바다거북',
        'animal_cards',
        1,
        '바다거북은 바다거북관에서 지내는 어류입니다. 해조류와 작은 먹이를 하루 한 번 먹습니다. 넓은 수조에서 유유히 헤엄치는 모습을 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['바다거북', '바다거북관', '해양', '수족관']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SHARK',
        '상어',
        'animal_cards',
        1,
        '상어는 상어관에서 지내는 어류입니다. 물고기 위주의 먹이를 하루 한 번 먹습니다. 수조 안을 끊임없이 헤엄치며 이동하는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['상어', '상어관', '해양', '수족관']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SNOWYOWL',
        '흰올빼미',
        'animal_cards',
        1,
        '흰올빼미는 흰올빼미관에서 지내는 조류입니다. 작은 먹이를 하루 한 번 공급받습니다. 하얀 깃털을 가지고 있으며 추운 환경을 좋아합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['흰올빼미', '흰올빼미관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SOFTSHELLTURTLE',
        '자라',
        'animal_cards',
        1,
        '자라는 자라관에서 지내는 파충류입니다. 물고기와 작은 먹이를 하루 한 번 먹습니다. 등딱지가 부드러운 것이 특징인 민물거북입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['자라', '자라관', '파충류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SQUIRREL',
        '다람쥐',
        'animal_cards',
        1,
        '다람쥐는 다람쥐관에서 지내는 잡식동물입니다. 견과류와 채소를 섞은 먹이를 하루 두 번 먹습니다. 먹이를 저장해 두는 습성이 있어 볼주머니가 발달했습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['다람쥐', '다람쥐관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SQUIRRELMONKEY',
        '다람쥐원숭이',
        'animal_cards',
        1,
        '다람쥐원숭이는 다람쥐원숭이관에서 지내는 잡식동물입니다. 과일과 곤충을 섞은 먹이를 하루 여러 번 나누어 먹습니다. 몸집이 작고 나무 사이를 재빠르게 이동합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['다람쥐원숭이', '다람쥐원숭이관', '잡식']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-STAGBEETLE',
        '사슴벌레',
        'animal_cards',
        1,
        '사슴벌레는 사슴벌레관에서 지내는 곤충입니다. 젤리 형태의 먹이를 하루 한 번 먹습니다. 집게 모양의 큰 턱을 가지고 있는 것이 특징입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['사슴벌레', '사슴벌레관', '곤충']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-STARFISH',
        '불가사리',
        'animal_cards',
        1,
        '불가사리는 불가사리관에서 지내는 어류입니다. 작은 해양생물을 하루 한 번 공급받습니다. 다섯 개의 팔을 이용해 천천히 이동합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['불가사리', '불가사리관', '해양', '수족관']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-STICKINSECT',
        '대벌레',
        'animal_cards',
        1,
        '대벌레는 대벌레관에서 지내는 곤충입니다. 나뭇잎 위주의 먹이를 하루 한 번 먹습니다. 나뭇가지와 비슷한 몸으로 위장하는 것이 특징입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['대벌레', '대벌레관', '곤충']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-STINGRAY',
        '가오리',
        'animal_cards',
        1,
        '가오리는 가오리관에서 지내는 어류입니다. 물고기와 갑각류를 섞은 먹이를 하루 한 번 먹습니다. 넓적한 몸으로 수조 바닥을 미끄러지듯 이동합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['가오리', '가오리관', '해양', '수족관']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-STORK',
        '황새',
        'animal_cards',
        1,
        '황새는 황새관에서 지내는 조류입니다. 물고기와 곡물을 섞은 먹이를 하루 두 번 먹습니다. 큰 둥지를 짓고 한 자리에 오래 머무는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['황새', '황새관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-SWAN',
        '백조',
        'animal_cards',
        1,
        '백조는 백조관에서 지내는 조류입니다. 수초와 곡물을 섞은 먹이를 하루 두 번 먹습니다. 연못 위를 유유히 헤엄치는 모습을 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['백조', '백조관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-TARANTULA',
        '타란튤라',
        'animal_cards',
        1,
        '타란튤라는 타란튤라관에서 지내는 곤충입니다. 작은 곤충을 하루 한 번 먹습니다. 몸 전체가 털로 덮여 있으며 야행성에 가깝습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['타란튤라', '타란튤라관', '곤충']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-TIGER',
        '호랑이',
        'animal_cards',
        1,
        '호랑이는 호랑이관 야외 방사장에서 지내는 육식동물입니다. 하루 한 번 정해진 시간에 고기 위주의 먹이를 먹으며, 물놀이를 즐기는 모습을 볼 수 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['호랑이', '호랑이관', '육식', '고기', '먹이', '방사장']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-TOAD',
        '두꺼비',
        'animal_cards',
        1,
        '두꺼비는 두꺼비관에서 지내는 양서류입니다. 작은 곤충을 하루 한 번 먹습니다. 피부에 오돌토돌한 돌기가 있는 것이 특징입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['두꺼비', '두꺼비관', '양서류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-TREEFROG',
        '청개구리',
        'animal_cards',
        1,
        '청개구리는 청개구리관에서 지내는 양서류입니다. 작은 곤충을 하루 한 번 먹습니다. 비 오는 날 울음소리를 크게 내는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['청개구리', '청개구리관', '양서류']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-TURKEY',
        '칠면조',
        'animal_cards',
        1,
        '칠면조는 칠면조관에서 지내는 조류입니다. 곡물과 채소를 섞은 먹이를 하루 두 번 먹습니다. 목 주위 피부색이 변하는 것이 특징입니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['칠면조', '칠면조관', '조류', '새']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-WALLABY',
        '왈라비',
        'animal_cards',
        1,
        '왈라비는 왈라비관에서 지내는 초식동물입니다. 건초와 채소 위주의 먹이를 하루 두 번 먹습니다. 캥거루보다 몸집이 작으며 무리를 지어 지냅니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['왈라비', '왈라비관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-WOLF',
        '늑대',
        'animal_cards',
        1,
        '늑대는 늑대관에서 지내는 육식동물입니다. 고기 위주의 먹이를 하루 한 번 먹습니다. 무리를 이루어 생활하며 서열에 따라 행동하는 습성이 있습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['늑대', '늑대관', '육식', '고기']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-WOMBAT',
        '웜뱃',
        'animal_cards',
        1,
        '웜뱃은 웜뱃관에서 지내는 초식동물입니다. 건초와 뿌리채소 위주의 먹이를 하루 한 번 먹습니다. 땅을 파고 굴을 만드는 습성이 있어 야행성에 가깝습니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['웜뱃', '웜뱃관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-YAK',
        '야크',
        'animal_cards',
        1,
        '야크는 야크관에서 지내는 초식동물입니다. 건초 위주의 먹이를 하루 두 번 먹습니다. 두꺼운 털을 가지고 있어 추운 환경에서도 잘 지냅니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['야크', '야크관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
INSERT INTO animal_cards (doc_id, title, collection, page, text, keywords)
VALUES (
        'ANIMAL-ZEBRA',
        '얼룩말',
        'animal_cards',
        1,
        '얼룩말은 얼룩말관에서 지내는 초식동물입니다. 건초와 풀 위주의 먹이를 하루 두 번 먹습니다. 무리를 지어 생활하며 줄무늬로 서로를 구분합니다. 이 카드는 교육용으로 작성된 자료이며 실제 개체별 운영 공지가 아닙니다.',
        ARRAY ['얼룩말', '얼룩말관', '초식', '건초']::text []
    ) ON CONFLICT (doc_id) DO
UPDATE
SET title = EXCLUDED.title,
    collection = EXCLUDED.collection,
    page = EXCLUDED.page,
    text = EXCLUDED.text,
    keywords = EXCLUDED.keywords;
COMMIT;