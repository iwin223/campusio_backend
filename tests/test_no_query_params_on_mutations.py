"""Regression guard: mutating endpoints must never declare bare scalar params.

FastAPI treats bare scalar parameters on POST/PUT/PATCH handlers as QUERY
parameters. The frontend sends JSON bodies, so such params either 422 the
request (required Query) or silently arrive as None/default (optional Query)
while the JSON body is ignored. This bug class caused real data loss
(e.g. student text submissions arriving empty).

Rule: every input to a mutating endpoint must be a path param, a Pydantic
request model (body), a File/Form upload, or a dependency. If this test
fails, wrap the offending scalars in a request model.
"""
import asyncio

from fastapi.routing import APIRoute

from server import app, register_routers


def _collect_offenders():
    asyncio.run(register_routers(app))
    offenders = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not (route.methods & {"POST", "PUT", "PATCH"}):
            continue
        query_params = [p.name for p in route.dependant.query_params]
        if query_params:
            offenders.append(
                f"{'/'.join(sorted(route.methods & {'POST', 'PUT', 'PATCH'}))} "
                f"{route.path} -> query params {query_params} "
                f"[{route.endpoint.__module__}.{route.endpoint.__name__}]"
            )
    return offenders


def test_no_query_params_on_mutating_routes():
    offenders = _collect_offenders()
    assert not offenders, (
        "Mutating routes must take request bodies, not query params. "
        "Wrap these scalars in a Pydantic/SQLModel request model:\n  "
        + "\n  ".join(offenders)
    )
