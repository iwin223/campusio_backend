import asyncio
from database import async_session
from models.user import User
from services.csv_import_service import CSVImportService
from sqlmodel import select

async def test():
    async with async_session() as session:
        r = await session.execute(select(User).where(User.email=='admin@school.edu.gh'))
        u = r.scalar_one_or_none()
        if not u:
            raise SystemExit('no user')
        csv = 'staff_id,first_name,last_name,email,phone,date_of_birth,gender,staff_type,position,department,qualification,date_joined,address,photo_url\n'
        csv += 'STF100,Test,Worker,test.worker@school.edu.gh,+233501234567,1985-01-01,male,teaching,Math,Math,MSc,2015-09-01,Accra,\n'
        svc = CSVImportService(session, u.school_id, u)
        res = await svc.import_staff(csv.encode('utf-8'))
        print('RESULT', res)

asyncio.run(test())
