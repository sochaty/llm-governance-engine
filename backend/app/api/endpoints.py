import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sqlalchemy import select, func
from app.models.benchmark import BenchmarkResult

@router.get("/benchmark/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    # 1. Get Total Savings (Sum of estimated_cost where provider is 'local')
    # Note: We calculate what it WOULD have cost on Cloud
    query_savings = select(func.sum(BenchmarkResult.estimated_cost)).where(BenchmarkResult.provider == 'local')
    
    # 2. Get Average Latency Comparison
    query_cloud_lat = select(func.avg(BenchmarkResult.latency_ms)).where(BenchmarkResult.provider == 'cloud')
    query_local_lat = select(func.avg(BenchmarkResult.latency_ms)).where(BenchmarkResult.provider == 'local')

    savings = (await db.execute(query_savings)).scalar() or 0.0
    avg_cloud = (await db.execute(query_cloud_lat)).scalar() or 0.0
    avg_local = (await db.execute(query_local_lat)).scalar() or 0.0

    return {
        "total_savings": round(savings, 4),
        "avg_cloud_latency": int(avg_cloud),
        "avg_local_latency": int(avg_local),
        "total_requests": (await db.execute(select(func.count(BenchmarkResult.id)))).scalar()
    }