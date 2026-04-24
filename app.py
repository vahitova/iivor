import streamlit as st
import graphviz
import random
import uuid

# ==========================================
# 1. НАСТРОЙКИ СТРАНИЦЫ И CSS
# ==========================================
st.set_page_config(page_title="Учим ИИ ловить вора", layout="wide")

# CSS для адаптации под интерактивную доску (крупный шрифт, карточки)
st.markdown("""
<style>
    .big-font { font-size: 24px !important; font-weight: bold; }
    .card { 
        border: 2px solid #ddd; border-radius: 10px; padding: 15px; 
        text-align: center; background-color: #f9f9f9; margin: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .emoji { font-size: 60px; }
    .thief-card { border-color: #ff4b4b; background-color: #ffeaea; }
    .good-card { border-color: #21c354; background-color: #eafbee; }
    .hidden-card { border-color: #888; background-color: #eee; }
    .stButton>button { width: 100%; font-size: 20px; padding: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ГЕНЕРАЦИЯ ДАННЫХ И ПРАВИЛА
# ==========================================
# ПЕДАГОГИКА: Мы задаем четкое скрытое правило для ИИ. 
# Вор — это тот, кто в КРАСНОМ и с ОЧКАМИ.
COLORS = {"red": "🔴 Красный", "blue": "🔵 Синий", "green": "🟢 Зеленый"}
GLASSES = {True: "👓 Есть очки", False: "🚫 Нет очков"}

def generate_suspect(id_num):
    color = random.choice(list(COLORS.keys()))
    has_glasses = random.choice([True, False])
    # Скрытое правило: Вор = Красный + Очки
    is_thief = (color == "red" and has_glasses)
    
    return {
        "id": id_num,
        "emoji": "🦹‍♂️" if is_thief else "👨‍💼", # Эмодзи просто для визуала, ИИ смотрит на признаки
        "color": color,
        "glasses": has_glasses,
        "is_thief": is_thief
    }

def generate_dataset(size=10):
    # Гарантируем, что в датасете будут и воры, и честные, чтобы дерево могло обучиться
    data = []
    while True:
        data = [generate_suspect(i) for i in range(size)]
        thieves = sum(1 for d in data if d["is_thief"])
        if 1 < thieves < size - 1: # Хотя бы 2 вора и 2 честных
            break
    return data

# ==========================================
# 3. ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ (SESSION STATE)
# ==========================================
if 'stage' not in st.session_state:
    st.session_state.stage = 1
    st.session_state.train_data = generate_dataset(10)
    st.session_state.test_data = generate_dataset(3)
    
    # Структура дерева: словарь узлов. 'root' - начальный узел.
    st.session_state.tree = {
        "root": {
            "data_indices": list(range(len(st.session_state.train_data))),
            "question": None, # Признак для разделения (напр. ("color", "red"))
            "yes_node": None,
            "no_node": None,
            "is_leaf": False,
            "prediction": None,
            "used_features": [] # Чтобы не спрашивать одно и то же дважды на ветке
        }
    }
    st.session_state.active_node = "root" # Узел, который сейчас делим
    
    # Для этапа 3
    st.session_state.test_card_idx = None
    st.session_state.test_current_node = "root"
    st.session_state.test_revealed = False

# ==========================================
# 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def render_card(suspect, hide_status=False):
    """Отрисовка карточки подозреваемого (HTML)"""
    color_name = COLORS[suspect["color"]]
    glasses_name = GLASSES[suspect["glasses"]]
    
    if hide_status:
        status_html = "<b>Статус:</b> ❓ Неизвестно"
        css_class = "hidden-card"
    else:
        if suspect["is_thief"]:
            status_html = "<b style='color:red;'>🧺 ВОР</b>"
            css_class = "thief-card"
        else:
            status_html = "<b style='color:green;'>✅ ЧЕСТНЫЙ</b>"
            css_class = "good-card"
            
    html = f"""
    <div class="card {css_class}">
        <div class="emoji">{suspect["emoji"]}</div>
        <div><b>Цвет:</b> {color_name}</div>
        <div><b>Очки:</b> {glasses_name}</div>
        <hr style="margin: 5px 0;">
        <div>{status_html}</div>
    </div>
    """
    return html

def check_purity(indices):
    """ПЕДАГОГИКА: Проверка 'чистоты' узла. Если все одинаковые — это Лист (ответ)."""
    if not indices: return True, "Пусто"
    thieves = sum(1 for i in indices if st.session_state.train_data[i]["is_thief"])
    if thieves == len(indices): return True, "ВОР"
    if thieves == 0: return True, "НЕ ВОР"
    return False, None

def build_graphviz():
    """Отрисовка дерева решений с помощью Graphviz"""
    dot = graphviz.Digraph(engine='dot')
    dot.attr(bgcolor='transparent')
    dot.attr('node', shape='box', style='filled', fontname='sans-serif', fontsize='14')
    
    for node_id, node in st.session_state.tree.items():
        if node["is_leaf"]:
            color = "#ffcccc" if node["prediction"] == "ВОР" else "#ccffcc"
            label = f"🧺 {node['prediction']}\n(Карточек: {len(node['data_indices'])})"
            dot.node(node_id, label, fillcolor=color, shape='ellipse')
        else:
            if node["question"]:
                feat_type, feat_val = node["question"]
                if feat_type == "color":
                    q_text = f"Цвет == {COLORS[feat_val].split(' ')[1]}?"
                else:
                    q_text = "Есть очки?"
                label = f"❓ {q_text}\n(Карточек: {len(node['data_indices'])})"
                dot.node(node_id, label, fillcolor="#e0e0ff")
                
                if node["yes_node"]:
                    dot.edge(node_id, node["yes_node"], label=" ДА", color="green", fontcolor="green")
                if node["no_node"]:
                    dot.edge(node_id, node["no_node"], label=" НЕТ", color="red", fontcolor="red")
            else:
                label = f"Выберите вопрос...\n(Карточек: {len(node['data_indices'])})"
                dot.node(node_id, label, fillcolor="#ffffe0", style="filled,dashed")
    return dot

# ==========================================
# 5. ЭКРАНЫ ПРИЛОЖЕНИЯ (ЭТАПЫ)
# ==========================================

def stage_1_ui():
    """ЭТАП 1: СБОР ДАННЫХ"""
    st.markdown('<p class="big-font">Этап 1: Сбор данных (Dataset)</p>', unsafe_allow_html=True)
    st.info("👩‍🏫 **Учитель:** Компьютер видит мир так — просто набор картинок и признаков. Наша задача — научить Искусственный Интеллект отличать вора от честного гражданина, задавая правильные вопросы.")
    
    cols = st.columns(5)
    for i, suspect in enumerate(st.session_state.train_data):
        with cols[i % 5]:
            st.markdown(render_card(suspect), unsafe_allow_html=True)
            
    st.write("---")
    if st.button("🚀 Перейти к обучению ИИ (Построение дерева)"):
        st.session_state.stage = 2
        st.rerun()

def stage_2_ui():
    """ЭТАП 2: ПОСТРОЕНИЕ ДЕРЕВА"""
    st.markdown('<p class="big-font">Этап 2: Обучение (Построение дерева решений)</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🌳 Текущее дерево ИИ")
        st.graphviz_chart(build_graphviz(), use_container_width=True)
        
    with col2:
        st.markdown("### ⚙️ Панель управления")
        
        # Ищем первый нерешенный узел
        active_node_id = None
        for n_id, n_data in st.session_state.tree.items():
            if not n_data["is_leaf"] and n_data["question"] is None:
                active_node_id = n_id
                break
                
        if active_node_id:
            node = st.session_state.tree[active_node_id]
            st.warning("⚠️ Есть ветка со смешанными карточками. Нужно задать вопрос!")
            
            # Показываем карточки в текущем узле
            st.write(f"Карточек в этой ветке: **{len(node['data_indices'])}**")
            
            # Собираем доступные вопросы
            all_questions = [
                ("color", "red", "Цвет: Красный?"),
                ("color", "blue", "Цвет: Синий?"),
                ("color", "green", "Цвет: Зеленый?"),
                ("glasses", True, "Есть очки?")
            ]
            
            # Фильтруем вопросы, которые уже задавались в этой ветке
            valid_questions = [q for q in all_questions if (q[0], q[1]) not in node["used_features"]]
            
            options = {f"{q[2]}": (q[0], q[1]) for q in valid_questions}
            selected_q_text = st.selectbox("Выберите признак для разделения:", list(options.keys()))
            
            if st.button("✂️ Разделить карточки"):
                feat_type, feat_val = options[selected_q_text]
                
                # ПЕДАГОГИКА: Разделяем данные на ДА и НЕТ
                yes_indices = []
                no_indices = []
                for idx in node["data_indices"]:
                    suspect = st.session_state.train_data[idx]
                    if suspect[feat_type] == feat_val:
                        yes_indices.append(idx)
                    else:
                        no_indices.append(idx)
                        
                # Проверка: если вопрос не делит (все ушли в одну сторону), ругаемся
                if len(yes_indices) == 0 or len(no_indices) == 0:
                    st.error("Этот вопрос не помогает разделить данные дальше! Выберите другой.")
                else:
                    # Обновляем текущий узел
                    node["question"] = (feat_type, feat_val)
                    
                    # Создаем дочерние узлы
                    yes_id = str(uuid.uuid4())
                    no_id = str(uuid.uuid4())
                    node["yes_node"] = yes_id
                    node["no_node"] = no_id
                    
                    new_used_features = node["used_features"].copy()
                    new_used_features.append((feat_type, feat_val))
                    
                    # Проверяем чистоту новых веток
                    yes_is_leaf, yes_pred = check_purity(yes_indices)
                    st.session_state.tree[yes_id] = {
                        "data_indices": yes_indices, "question": None, 
                        "yes_node": None, "no_node": None,
                        "is_leaf": yes_is_leaf, "prediction": yes_pred,
                        "used_features": new_used_features
                    }
                    
                    no_is_leaf, no_pred = check_purity(no_indices)
                    st.session_state.tree[no_id] = {
                        "data_indices": no_indices, "question": None,
                        "yes_node": None, "no_node": None,
                        "is_leaf": no_is_leaf, "prediction": no_pred,
                        "used_features": new_used_features
                    }
                    st.rerun()
        else:
            st.success("🎉 Дерево полностью обучено! Все ветки ведут к четкому ответу.")
            if st.button("🎯 Перейти к Тестированию (Инференс)"):
                st.session_state.stage = 3
                st.rerun()

def stage_3_ui():
    """ЭТАП 3: ТЕСТИРОВАНИЕ (INFERENCE)"""
    st.markdown('<p class="big-font">Этап 3: Тестирование (Inference)</p>', unsafe_allow_html=True)
    st.info("👩‍🏫 **Учитель:** Теперь проверим, как ИИ работает на новых данных. Выберите подозреваемого и проведите его по дереву!")
    
    col_test, col_tree = st.columns([1, 2])
    
    with col_test:
        st.markdown("### Новые подозреваемые")
        # Выбор карточки для теста
        cols = st.columns(3)
        for i, suspect in enumerate(st.session_state.test_data):
            with cols[i]:
                st.markdown(render_card(suspect, hide_status=True), unsafe_allow_html=True)
                if st.button(f"Выбрать #{i+1}", key=f"sel_{i}"):
                    st.session_state.test_card_idx = i
                    st.session_state.test_current_node = "root"
                    st.session_state.test_revealed = False
                    st.rerun()
                    
        if st.session_state.test_card_idx is not None:
            st.write("---")
            st.markdown("### 🔍 Проверка:")
            current_suspect = st.session_state.test_data[st.session_state.test_card_idx]
            
            if st.session_state.test_revealed:
                st.markdown(render_card(current_suspect, hide_status=False), unsafe_allow_html=True)
            else:
                st.markdown(render_card(current_suspect, hide_status=True), unsafe_allow_html=True)
                
            node = st.session_state.tree[st.session_state.test_current_node]
            
            # ПЕДАГОГИКА: Пошаговый проход по дереву (Инференс)
            if not node["is_leaf"]:
                feat_type, feat_val = node["question"]
                if feat_type == "color":
                    q_text = f"Цвет этого персонажа == {COLORS[feat_val].split(' ')[1]}?"
                else:
                    q_text = "У этого персонажа есть очки?"
                    
                st.write(f"**Вопрос ИИ:** {q_text}")
                
                # Кнопки для продвижения по дереву
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ ДА", use_container_width=True):
                        if current_suspect[feat_type] == feat_val:
                            st.session_state.test_current_node = node["yes_node"]
                            st.rerun()
                        else:
                            st.error("Внимательнее! Посмотрите на карточку.")
                with c2:
                    if st.button("❌ НЕТ", use_container_width=True):
                        if current_suspect[feat_type] != feat_val:
                            st.session_state.test_current_node = node["no_node"]
                            st.rerun()
                        else:
                            st.error("Внимательнее! Посмотрите на карточку.")
            else:
                st.success(f"🤖 **Предсказание ИИ:** {node['prediction']}")
                if not st.session_state.test_revealed:
                    if st.button("Узнать правду (Проверить ответ)"):
                        st.session_state.test_revealed = True
                        st.rerun()
                else:
                    actual = "ВОР" if current_suspect["is_thief"] else "НЕ ВОР"
                    if node['prediction'] == actual:
                        st.balloons()
                        st.success("✅ Верно! ИИ справился.")
                    else:
                        st.error("❌ Ошибка! Дерево обучилось неидеально (или данные противоречивы).")
                        
    with col_tree:
        st.markdown("### 🌳 Дерево")
        st.graphviz_chart(build_graphviz(), use_container_width=True)

    st.write("---")
    if st.button("🔄 Начать весь урок заново"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ==========================================
# 6. РОУТИНГ ЭКРАНОВ
# ==========================================
if st.session_state.stage == 1:
    stage_1_ui()
elif st.session_state.stage == 2:
    stage_2_ui()
elif st.session_state.stage == 3:
    stage_3_ui()
