import streamlit as st
import graphviz
import random

# ==========================================
# 0. НАСТРОЙКИ СТРАНИЦЫ И CSS
# ==========================================
st.set_page_config(page_title="Учим ИИ ловить вора!", layout="wide", page_icon="🕵️‍♂️")

# CSS для стилизации карточек подозреваемых (крупные шрифты, адаптивность для проектора)
st.markdown("""
<style>
    .card {
        border: 2px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        background-color: #f9f9f9;
        margin-bottom: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .emoji { font-size: 50px; }
    .thief { border-color: #ff4b4b; background-color: #ffeaea; }
    .innocent { border-color: #4CAF50; background-color: #eafbee; }
    .hidden { background-color: #eee; border-color: #999; }
    .attr { font-size: 18px; font-weight: bold; }
    .badge { 
        display: inline-block; padding: 5px 10px; 
        border-radius: 15px; font-size: 14px; margin-top: 10px;
        color: white; font-weight: bold;
    }
    .badge-thief { background-color: #ff4b4b; }
    .badge-innocent { background-color: #4CAF50; }
    .badge-unknown { background-color: #888; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 1. ДАННЫЕ И СОСТОЯНИЕ (SESSION STATE)
# ==========================================

# Все доступные признаки
FEATURES = ['Цвет: Красный 🔴', 'Цвет: Синий 🔵', 'Цвет: Зеленый 🟢', 'Есть очки 👓']

# Правило для генерации: Вор = Красный И в Очках
def generate_person(id_num, is_test=False):
    colors = ['🔴', '🔵', '🟢']
    color = random.choice(colors)
    glasses = random.choice([True, False])
    
    # Намеренно создаем баланс для обучающей выборки
    if not is_test:
        if id_num in [1, 2]: # Точно воры
            color, glasses = '🔴', True
        elif id_num in [3, 4]: # Точно не воры (красный, но без очков)
            color, glasses = '🔴', False
        elif id_num in [5, 6]: # Точно не воры (в очках, но не красные)
            color = random.choice(['🔵', '🟢'])
            glasses = True
            
    is_thief = (color == '🔴' and glasses)
    
    return {
        "id": id_num,
        "emoji": "👤",
        "color": color,
        "glasses": glasses,
        "is_thief": is_thief
    }

# Инициализация состояния
if 'stage' not in st.session_state:
    st.session_state.stage = 1
    # Этап 1: Данные
    st.session_state.train_data = [generate_person(i) for i in range(1, 9)]
    random.shuffle(st.session_state.train_data)
    
    # Этап 2: Дерево
    st.session_state.tree = {
        'id': 'root',
        'data': st.session_state.train_data,
        'feature': None,
        'yes_node': None,
        'no_node': None,
        'used_features': [],
        'is_pure': False,
        'prediction': None
    }
    
    # Этап 3: Тесты
    st.session_state.test_data = [generate_person(i, is_test=True) for i in range(9, 12)]
    st.session_state.test_data[0]['is_thief'] = True # Гарантируем одного вора в тестах
    st.session_state.test_data[0]['color'] = '🔴'
    st.session_state.test_data[0]['glasses'] = True
    random.shuffle(st.session_state.test_data)
    
    st.session_state.active_test_card = None
    st.session_state.test_node_id = 'root'
    st.session_state.test_finished = False

def restart_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def render_card(person, hide_label=False):
    """Отрисовка HTML карточки подозреваемого"""
    glasses_text = "👓 Да" if person['glasses'] else "Нет"
    
    if hide_label:
        css_class = "card hidden"
        badge = "<div class='badge badge-unknown'>❓ Кто это?</div>"
    else:
        css_class = "card thief" if person['is_thief'] else "card innocent"
        badge = "<div class='badge badge-thief'>🧺 ВОР</div>" if person['is_thief'] else "<div class='badge badge-innocent'>✅ ЧЕСТНЫЙ</div>"

    html = f"""
    <div class="{css_class}">
        <div class="emoji">{person['emoji']}</div>
        <div class="attr">Цвет одежды: {person['color']}</div>
        <div class="attr">Очки: {glasses_text}</div>
        {badge}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def check_condition(person, feature):
    """Проверка карточки на соответствие выбранному признаку"""
    if feature == 'Цвет: Красный 🔴': return person['color'] == '🔴'
    if feature == 'Цвет: Синий 🔵': return person['color'] == '🔵'
    if feature == 'Цвет: Зеленый 🟢': return person['color'] == '🟢'
    if feature == 'Есть очки 👓': return person['glasses'] == True
    return False

def check_purity(data):
    """Проверка: все ли в группе одинаковые (только воры или только честные)"""
    if len(data) == 0: return True, "Пусто"
    thieves = sum(1 for p in data if p['is_thief'])
    if thieves == len(data): return True, "ВОР"
    if thieves == 0: return True, "ЧЕСТНЫЙ"
    return False, "Смешано"

def find_unsplit_node(node):
    """Рекурсивный поиск узла, который нуждается в разделении"""
    if node['is_pure']: return None
    if node['feature'] is None: return node
    
    left = find_unsplit_node(node['yes_node'])
    if left: return left
    
    right = find_unsplit_node(node['no_node'])
    if right: return right
    
    return None

def build_graph(node, dot=None):
    """Построение визуализации Graphviz"""
    if dot is None:
        dot = graphviz.Digraph(engine='dot')
        dot.attr(size='10,10!', rankdir='TB', nodesep='0.5', ranksep='0.8')
        dot.attr('node', shape='box', style='rounded,filled', fontname='Arial', fontsize='14')

    node_id = node['id']
    
    if node['is_pure']:
        color = '#ffcccc' if node['prediction'] == "ВОР" else '#ccffcc'
        label = f"🧺 {node['prediction']}\n(Карточек: {len(node['data'])})"
        dot.node(node_id, label, fillcolor=color, shape='cylinder')
    else:
        if node['feature']:
            label = f"❓ {node['feature']}"
            dot.node(node_id, label, fillcolor='#cce5ff', shape='diamond')
            
            # Рекурсия для детей
            build_graph(node['yes_node'], dot)
            build_graph(node['no_node'], dot)
            
            dot.edge(node_id, node['yes_node']['id'], label=" ДА", color="green", fontcolor="green", penwidth="2")
            dot.edge(node_id, node['no_node']['id'], label=" НЕТ", color="red", fontcolor="red", penwidth="2")
        else:
            dot.node(node_id, f"Здесь нужно\nзадать вопрос\n(Карточек: {len(node['data'])})", fillcolor='#ffffcc', style='dashed,filled')

    return dot

# ==========================================
# 3. ЭТАПЫ ПРИЛОЖЕНИЯ
# ==========================================

# --- ЭТАП 1: СБОР ДАННЫХ ---
if st.session_state.stage == 1:
    st.title("🕵️‍♂️ ЭТАП 1: Сбор данных (Датасет)")
    st.info("🎓 **Учитель:** Компьютер видит мир не так, как мы. Для него это просто набор характеристик. "
            "Наша задача — собрать данные о подозреваемых, чтобы научить Искусственный Интеллект (ИИ) отличать вора от честного гражданина.")
    
    st.markdown("### 📋 Доска подозреваемых (исторические данные)")
    
    # Вывод карточек сеткой (по 4 в ряд)
    cols = st.columns(4)
    for i, person in enumerate(st.session_state.train_data):
        with cols[i % 4]:
            render_card(person)
            
    st.write("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 ДАННЫЕ СОБРАНЫ -> ПЕРЕЙТИ К ОБУЧЕНИЮ ИИ", use_container_width=True, type="primary"):
            st.session_state.stage = 2
            st.rerun()

# --- ЭТАП 2: ПОСТРОЕНИЕ ДЕРЕВА ---
elif st.session_state.stage == 2:
    st.title("🌳 ЭТАП 2: Обучение (Строим дерево решений)")
    st.info("🎓 **Учитель:** ИИ учится, задавая вопросы, на которые можно ответить 'ДА' или 'НЕТ'. "
            "Мы должны разделить карточки так, чтобы в конце в каждой группе остались ЛИБО только воры, ЛИБО только честные (чистые корзины).")

    active_node = find_unsplit_node(st.session_state.tree)

    col_tree, col_ui = st.columns([1.5, 1])

    with col_tree:
        st.markdown("### 🗺️ Карта мозга нашего ИИ")
        dot = build_graph(st.session_state.tree)
        st.graphviz_chart(dot)

    with col_ui:
        if active_node is not None:
            st.markdown("### 🛠️ Разделяем смешанную группу")
            st.write(f"В этой группе **{len(active_node['data'])}** подозреваемых. Они смешаны!")
            
            # Показываем карточки активного узла
            scroll_container = st.container(height=300, border=True)
            with scroll_container:
                for p in active_node['data']:
                    render_card(p)

            # Выбор признака (исключая уже использованные в этой ветке)
            available_features = [f for f in FEATURES if f not in active_node['used_features']]
            
            selected_feature = st.selectbox("Выберите вопрос для разделения:", available_features)
            
            if st.button("✂️ РАЗДЕЛИТЬ", type="primary"):
                active_node['feature'] = selected_feature
                
                # Разделение данных
                yes_data = [p for p in active_node['data'] if check_condition(p, selected_feature)]
                no_data = [p for p in active_node['data'] if not check_condition(p, selected_feature)]
                
                # Создание дочерних узлов
                new_used_features = active_node['used_features'] + [selected_feature]
                
                for side, data_subset, prefix in [('yes_node', yes_data, 'yes'), ('no_node', no_data, 'no')]:
                    is_pure, pred = check_purity(data_subset)
                    active_node[side] = {
                        'id': f"{active_node['id']}_{prefix}",
                        'data': data_subset,
                        'feature': None,
                        'yes_node': None,
                        'no_node': None,
                        'used_features': new_used_features,
                        'is_pure': is_pure,
                        'prediction': pred if is_pure else None
                    }
                st.rerun()
        else:
            st.success("🎉 УРА! Все ветки дерева закончились чистыми корзинами! ИИ обучен.")
            if st.button("🧪 ПЕРЕЙТИ К ТЕСТИРОВАНИЮ", use_container_width=True, type="primary"):
                st.session_state.stage = 3
                st.rerun()

# --- ЭТАП 3: ТЕСТИРОВАНИЕ (INFERENCE) ---
elif st.session_state.stage == 3:
    st.title("🎯 ЭТАП 3: Тестирование (Инференс)")
    st.info("🎓 **Учитель:** Время проверить наш ИИ! На улице появились новые люди. Мы не знаем, кто они. "
            "Давайте пропустим их через наше Дерево Решений и посмотрим, угадает ли компьютер!")

    # 1. Выбор карточки
    st.markdown("### 1️⃣ Выберите подозреваемого для проверки")
    cols = st.columns(3)
    for i, person in enumerate(st.session_state.test_data):
        with cols[i]:
            render_card(person, hide_label=True)
            if st.button(f"Проверить №{person['id']}", key=f"btn_{person['id']}", use_container_width=True):
                st.session_state.active_test_card = person
                st.session_state.test_node_id = 'root'
                st.session_state.test_finished = False
                st.rerun()

    st.write("---")

    # 2. Проход по дереву
    if st.session_state.active_test_card is not None:
        test_person = st.session_state.active_test_card
        
        col_test_card, col_test_tree = st.columns([1, 2])
        
        with col_test_card:
            st.markdown("### Текущий подозреваемый:")
            # Показываем атрибуты, но скрываем статус вора до конца
            render_card(test_person, hide_label=not st.session_state.test_finished)

        with col_test_tree:
            st.markdown("### 🤖 Проход по дереву")
            
            # Функция для поиска текущего узла по ID
            def get_node_by_id(node, target_id):
                if node['id'] == target_id: return node
                if node['yes_node']:
                    res = get_node_by_id(node['yes_node'], target_id)
                    if res: return res
                if node['no_node']:
                    res = get_node_by_id(node['no_node'], target_id)
                    if res: return res
                return None

            current_node = get_node_by_id(st.session_state.tree, st.session_state.test_node_id)

            if not current_node['is_pure']:
                st.warning(f"ИИ спрашивает: **{current_node['feature']}**?")
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🟢 Ответить: ДА", use_container_width=True):
                        st.session_state.test_node_id = current_node['yes_node']['id']
                        st.rerun()
                with c2:
                    if st.button("🔴 Ответить: НЕТ", use_container_width=True):
                        st.session_state.test_node_id = current_node['no_node']['id']
                        st.rerun()
            else:
                st.session_state.test_finished = True
                prediction = current_node['prediction']
                actual = "ВОР" if test_person['is_thief'] else "ЧЕСТНЫЙ"
                
                st.markdown(f"### 🤖 Предсказание ИИ: **{prediction}**")
                
                if prediction == actual:
                    st.success("✅ ИИ ответил АБСОЛЮТНО ВЕРНО! Дерево работает отлично!")
                    st.balloons()
                else:
                    st.error(f"❌ ОШИБКА ИИ! На самом деле это {actual}. Возможно, мы собрали мало данных или задали плохие вопросы.")

    st.write("---")
    if st.button("🔄 НАЧАТЬ ВСЁ СНАЧАЛА (Сброс)", type="secondary"):
        restart_app()
