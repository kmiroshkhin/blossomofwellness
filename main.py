import os
from contextlib import contextmanager
from datetime import date, timedelta

from nicegui import ui
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


PRIMARY = 'emerald'
APP_VERSION = '2026-05-17-fitness-competition-mvp-v2-ui-upgrade'

ui.add_head_html('''
<style>
body {
    background:
        linear-gradient(rgba(250,250,250,0.90), rgba(248,248,248,0.95)),
        url("https://images.unsplash.com/photo-1518611012118-696072aa579a?q=80&w=1800&auto=format&fit=crop")
        center center / cover fixed;
    font-family: "Inter", sans-serif;
}

.hero-card {
    background: rgba(255,255,255,0.86);
    backdrop-filter: blur(12px);
    border-radius: 28px;
    box-shadow: 0 12px 35px rgba(0,0,0,0.10);
    border: 1px solid rgba(255,255,255,0.65);
}

.score-card {
    background: linear-gradient(135deg, #ffffff, #f7faf7);
    border-radius: 24px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.09);
    border: 1px solid rgba(0,0,0,0.05);
}

.checkin-card {
    background: rgba(255,255,255,0.88);
    backdrop-filter: blur(12px);
    border-radius: 24px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.09);
}

.hero-title {
    font-size: 46px;
    font-weight: 850;
    line-height: 1.05;
}

.hero-subtitle {
    font-size: 21px;
    color: #4b5563;
}

.section-title {
    font-size: 28px;
    font-weight: 750;
}

.winner-text {
    color: #d97706;
    font-weight: 800;
    font-size: 22px;
}

.kirill-button button {
    background: linear-gradient(135deg, #047857, #10b981) !important;
    color: white !important;
    border-radius: 20px !important;
    font-weight: 800;
    height: 64px;
    font-size: 17px;
    box-shadow: 0 8px 22px rgba(16,185,129,0.35);
}

.flor-button button {
    background: linear-gradient(135deg, #db2777, #f472b6) !important;
    color: white !important;
    border-radius: 20px !important;
    font-weight: 800;
    height: 64px;
    font-size: 17px;
    box-shadow: 0 8px 22px rgba(244,114,182,0.35);
}

.leaderboard-button button {
    border-radius: 20px !important;
    height: 58px;
    font-weight: 800;
    font-size: 16px;
}

.glow {
    animation: glowPulse 2.4s infinite ease-in-out;
}

@keyframes glowPulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.015); }
    100% { transform: scale(1); }
}

@media (max-width: 640px) {
    .hero-title {
        font-size: 36px;
    }
    .hero-subtitle {
        font-size: 18px;
    }
}
</style>
''')

print(f'Starting Blossom of Wellness: {APP_VERSION}')

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL is not set.')

KIRILL_PASSWORD = os.getenv('KIRILL_PASSWORD')
FLOR_PASSWORD = os.getenv('FLOR_PASSWORD')
if not KIRILL_PASSWORD or not FLOR_PASSWORD:
    raise RuntimeError('KIRILL_PASSWORD and FLOR_PASSWORD must be set.')

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


@contextmanager
def get_conn():
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def calculate_daily_score(
    check_in_date: date,
    sleep_target_met: bool,
    strain_target_met: bool,
    protein_target_met: bool,
    calorie_target_met: bool,
    alcohol_consumed: bool,
) -> int:
    score = 0

    is_friday = check_in_date.weekday() == 4
    is_saturday = check_in_date.weekday() == 5

    if sleep_target_met or is_saturday:
        score += 1
    if strain_target_met:
        score += 1
    if protein_target_met:
        score += 1
    if calorie_target_met:
        score += 1

    if alcohol_consumed and not is_friday:
        score -= 3

    return score


def test_db_connection() -> tuple[bool, str]:
    try:
        with get_conn() as conn:
            conn.execute(text('select 1'))
        return True, 'Database connected.'
    except SQLAlchemyError as exc:
        return False, f'Connection failed: {exc}'


def save_checkin(
    participant_name: str,
    sleep_target_met: bool,
    strain_target_met: bool,
    protein_target_met: bool,
    calorie_target_met: bool,
    alcohol_consumed: bool,
) -> dict:
    today = date.today()
    daily_score = calculate_daily_score(
        today,
        sleep_target_met,
        strain_target_met,
        protein_target_met,
        calorie_target_met,
        alcohol_consumed,
    )

    sql = text("""
        insert into public.fitness_competition_checkins (
            participant_name,
            check_in_date,
            sleep_target_met,
            strain_target_met,
            protein_target_met,
            calorie_target_met,
            alcohol_consumed,
            daily_score
        )
        values (
            :participant_name,
            :check_in_date,
            :sleep_target_met,
            :strain_target_met,
            :protein_target_met,
            :calorie_target_met,
            :alcohol_consumed,
            :daily_score
        )
        on conflict (participant_name, check_in_date)
        do update set
            sleep_target_met = excluded.sleep_target_met,
            strain_target_met = excluded.strain_target_met,
            protein_target_met = excluded.protein_target_met,
            calorie_target_met = excluded.calorie_target_met,
            alcohol_consumed = excluded.alcohol_consumed,
            daily_score = excluded.daily_score,
            updated_at = now()
        returning *
    """)

    payload = {
        'participant_name': participant_name,
        'check_in_date': today.isoformat(),
        'sleep_target_met': sleep_target_met,
        'strain_target_met': strain_target_met,
        'protein_target_met': protein_target_met,
        'calorie_target_met': calorie_target_met,
        'alcohol_consumed': alcohol_consumed,
        'daily_score': daily_score,
    }

    with get_conn() as conn:
        row = conn.execute(sql, payload).mappings().first()
        conn.commit()
        return dict(row)


def get_weekly_rows() -> list[dict]:
    start = week_start(date.today())
    end = start + timedelta(days=6)

    sql = text("""
        select *
        from public.fitness_competition_checkins
        where check_in_date between :start_date and :end_date
        order by check_in_date asc, participant_name asc
    """)

    with get_conn() as conn:
        rows = conn.execute(sql, {
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
        }).mappings().all()
        return [dict(row) for row in rows]


def get_weekly_scores() -> dict:
    rows = get_weekly_rows()
    scores = {'Kirill': 0, 'Flor': 0}

    for row in rows:
        name = row['participant_name']
        scores[name] = scores.get(name, 0) + int(row['daily_score'] or 0)

    return scores


def page_shell(title: str, subtitle: str, back_route: str | None = None):
    with ui.column().classes('w-full max-w-5xl mx-auto p-6 gap-6'):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-3'):
                ui.icon('local_florist', color=PRIMARY).classes('text-4xl')
                with ui.column().classes('gap-0'):
                    ui.label('Blossom of Wellness').classes('text-2xl font-bold')
                    ui.label('Kirill vs Flor Fitness Challenge').classes('text-gray-600')
            if back_route:
                ui.button('Back', on_click=lambda: ui.navigate.to(back_route), icon='arrow_back').props('outline')

        ui.label(title).classes('text-3xl font-bold')
        ui.label(subtitle).classes('text-lg text-gray-700')


@ui.page('/')
def landing_page():
    ok, message = test_db_connection()
    scores = get_weekly_scores()

    kirill_score = scores.get('Kirill', 0)
    flor_score = scores.get('Flor', 0)

    if kirill_score > flor_score:
        leader = 'Kirill 🌱'
    elif flor_score > kirill_score:
        leader = 'Flor 🌸'
    else:
        leader = 'Tie 🤝'

    with ui.column().classes('w-full max-w-5xl mx-auto p-6 gap-6'):

        with ui.card().classes('hero-card w-full p-10 glow'):
            ui.label('Blossom of Wellness').classes('hero-title')
            ui.label('Discipline. Competition. Growth.').classes('hero-subtitle')

            ui.separator()

            ui.label('Kirill 🌱 vs Flor 🌸').classes('text-3xl font-bold')
            ui.label('Weekly Fitness Challenge').classes('text-xl text-gray-600')
            ui.label(f'Current Leader: {leader}').classes('winner-text mt-4')

        with ui.card().classes('score-card w-full p-8'):
            ui.label('Current Weekly Score').classes('section-title')
            ui.separator()

            ui.label(f'Kirill 🌱 — {kirill_score} points').classes('text-2xl font-semibold text-emerald-700')
            ui.linear_progress(value=min(kirill_score / 28, 1.0)).props('color=positive').classes('w-full')

            ui.space()

            ui.label(f'Flor 🌸 — {flor_score} points').classes('text-2xl font-semibold text-pink-500')
            ui.linear_progress(value=min(flor_score / 28, 1.0)).props('color=pink').classes('w-full')

        with ui.column().classes('w-full gap-4'):
            ui.button(
                'KIRILL CHECK-IN 🌱',
                on_click=lambda: ui.navigate.to('/login/Kirill')
            ).classes('w-full kirill-button')

            ui.button(
                'FLOR CHECK-IN 🌸',
                on_click=lambda: ui.navigate.to('/login/Flor')
            ).classes('w-full flor-button')

            ui.button(
                'VIEW LEADERBOARD 🏆',
                on_click=lambda: ui.navigate.to('/leaderboard')
            ).props('outline').classes('w-full leaderboard-button')

        ui.label(message).classes(f"text-sm {'text-green-700' if ok else 'text-red-600'}")
        ui.label(f'Version: {APP_VERSION}').classes('text-xs text-gray-500')


@ui.page('/login/{participant_name}')
def login_page(participant_name: str):
    if participant_name not in ['Kirill', 'Flor']:
        page_shell('Invalid Participant', 'Please return home.', '/')
        return

    page_shell(f'{participant_name} Login', 'Enter your password to continue.', '/')

    with ui.card().classes('checkin-card w-full max-w-xl mx-auto p-6'):
        password = ui.input('Password', password=True, password_toggle_button=True).classes('w-full')

        def login():
            expected = KIRILL_PASSWORD if participant_name == 'Kirill' else FLOR_PASSWORD

            if password.value != expected:
                ui.notify('Invalid password', type='negative')
                return

            ui.navigate.to(f'/checkin/{participant_name}')

        ui.button('Continue', on_click=login).classes('w-full')


@ui.page('/checkin/{participant_name}')
def checkin_page(participant_name: str):
    if participant_name not in ['Kirill', 'Flor']:
        page_shell('Invalid Participant', 'Please return home.', '/')
        return

    today = date.today()
    is_friday = today.weekday() == 4
    is_saturday = today.weekday() == 5

    page_shell(
        f'{participant_name} Daily Check-In',
        'Mark yes or no for today’s competition vector.',
        '/',
    )

    with ui.card().classes('checkin-card w-full max-w-2xl mx-auto p-6 gap-5'):
        if is_friday:
            ui.label('Friday cheat day: alcohol has no penalty today.').classes('text-amber-700 font-semibold')

        if is_saturday:
            ui.label('Saturday recovery rule: sleep target is automatically credited today.').classes('text-emerald-700 font-semibold')

        sleep = ui.checkbox('Sleep target above 75%? (+1)').classes('text-lg')
        strain = ui.checkbox('Daily strain target met? (+1)').classes('text-lg')
        protein = ui.checkbox('Daily protein intake met? (+1)').classes('text-lg')
        calories = ui.checkbox('Daily calorie target met? (+1)').classes('text-lg')
        alcohol = ui.checkbox('Alcohol consumed? (-3, except Friday)').classes('text-lg')

        if is_saturday:
            sleep.set_value(True)
            sleep.disable()

        result = ui.column().classes('w-full gap-3')

        def submit():
            result.clear()

            row = save_checkin(
                participant_name,
                bool(sleep.value),
                bool(strain.value),
                bool(protein.value),
                bool(calories.value),
                bool(alcohol.value),
            )

            with result:
                ui.notify('Check-in saved', type='positive')
                with ui.card().classes('w-full p-4 bg-green-50'):
                    ui.label(f"Saved for {participant_name}: {row['daily_score']} points today").classes('text-xl font-semibold')
                    ui.button('View Leaderboard', on_click=lambda: ui.navigate.to('/leaderboard')).classes('w-full')

        ui.button('Submit Check-In', on_click=submit).classes('w-full')


@ui.page('/leaderboard')
def leaderboard_page():
    start = week_start(date.today())
    end = start + timedelta(days=6)

    page_shell(
        'Weekly Leaderboard',
        f'Week of {start.isoformat()} through {end.isoformat()}',
        '/',
    )

    rows = get_weekly_rows()
    scores = get_weekly_scores()

    kirill_score = scores.get('Kirill', 0)
    flor_score = scores.get('Flor', 0)

    with ui.card().classes('score-card w-full p-8 glow'):
        ui.label('Current Score').classes('text-2xl font-bold')
        ui.label(f'Kirill 🌱: {kirill_score} points').classes('text-lg text-emerald-700 font-semibold')
        ui.label(f'Flor 🌸: {flor_score} points').classes('text-lg text-pink-500 font-semibold')

        if kirill_score > flor_score:
            ui.label('Current leader: Kirill 🌱').classes('winner-text')
        elif flor_score > kirill_score:
            ui.label('Current leader: Flor 🌸').classes('winner-text')
        else:
            ui.label('Currently tied 🤝').classes('text-amber-700 font-semibold')

    ui.separator()
    ui.label('Daily History').classes('text-xl font-semibold')

    if not rows:
        ui.label('No check-ins yet this week.')
        return

    for row in rows:
        with ui.card().classes('score-card w-full p-4'):
            ui.label(f"{row['check_in_date']} — {row['participant_name']}").classes('font-semibold')
            ui.label(f"Daily score: {row['daily_score']}")
            ui.label(f"Sleep: {'Yes' if row['sleep_target_met'] else 'No'}")
            ui.label(f"Strain: {'Yes' if row['strain_target_met'] else 'No'}")
            ui.label(f"Protein: {'Yes' if row['protein_target_met'] else 'No'}")
            ui.label(f"Calories: {'Yes' if row['calorie_target_met'] else 'No'}")
            ui.label(f"Alcohol: {'Yes' if row['alcohol_consumed'] else 'No'}")


ui.run(
    host='0.0.0.0',
    port=int(os.environ.get('PORT', 8080)),
    title='Blossom of Wellness',
    reload=False,
)