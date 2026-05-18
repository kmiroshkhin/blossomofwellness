import os
from contextlib import contextmanager
from datetime import date, timedelta

from nicegui import ui
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


PRIMARY = 'emerald'
APP_VERSION = '2026-05-17-fitness-competition-mvp-v1'

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
    with ui.column().classes('w-full max-w-4xl mx-auto p-6 gap-6'):
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
    page_shell('Weekly Fitness Challenge', 'Daily check-ins. Weekly winner. Blossom energy.')

    ok, message = test_db_connection()
    ui.label(message).classes(f"text-sm {'text-green-700' if ok else 'text-red-600'}")

    scores = get_weekly_scores()

    with ui.card().classes('w-full p-5'):
        ui.label('Current Weekly Score').classes('text-xl font-semibold')
        ui.label(f"Kirill: {scores.get('Kirill', 0)} points")
        ui.label(f"Flor: {scores.get('Flor', 0)} points")

    with ui.column().classes('w-full gap-4'):
        ui.button('Kirill Check-In', on_click=lambda: ui.navigate.to('/login/Kirill')).classes('w-full')
        ui.button('Flor Check-In', on_click=lambda: ui.navigate.to('/login/Flor')).classes('w-full')
        ui.button('View Leaderboard', on_click=lambda: ui.navigate.to('/leaderboard')).classes('w-full').props('outline')

    ui.label(f'Version: {APP_VERSION}').classes('text-xs text-gray-500')


@ui.page('/login/{participant_name}')
def login_page(participant_name: str):
    if participant_name not in ['Kirill', 'Flor']:
        page_shell('Invalid Participant', 'Please return home.', '/')
        return

    page_shell(f'{participant_name} Login', 'Enter your password to continue.', '/')

    password = ui.input('Password', password=True, password_toggle_button=True).classes('w-full max-w-lg')

    def login():
        expected = KIRILL_PASSWORD if participant_name == 'Kirill' else FLOR_PASSWORD

        if password.value != expected:
            ui.notify('Invalid password', type='negative')
            return

        ui.navigate.to(f'/checkin/{participant_name}')

    ui.button('Continue', on_click=login).classes('w-full max-w-lg')


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
            ui.card().classes('w-full p-4').classes('bg-green-50')
            ui.label(f"Saved for {participant_name}: {row['daily_score']} points today").classes('text-xl font-semibold')
            ui.button('View Leaderboard', on_click=lambda: ui.navigate.to('/leaderboard')).classes('w-full')

    ui.button('Submit Check-In', on_click=submit).classes('w-full max-w-lg')


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

    with ui.card().classes('w-full p-5'):
        ui.label('Current Score').classes('text-2xl font-bold')
        ui.label(f'Kirill: {kirill_score} points').classes('text-lg')
        ui.label(f'Flor: {flor_score} points').classes('text-lg')

        if kirill_score > flor_score:
            ui.label('Current leader: Kirill 🌱').classes('text-green-700 font-semibold')
        elif flor_score > kirill_score:
            ui.label('Current leader: Flor 🌸').classes('text-green-700 font-semibold')
        else:
            ui.label('Currently tied 🤝').classes('text-amber-700 font-semibold')

    ui.separator()
    ui.label('Daily History').classes('text-xl font-semibold')

    if not rows:
        ui.label('No check-ins yet this week.')
        return

    for row in rows:
        with ui.card().classes('w-full p-4'):
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