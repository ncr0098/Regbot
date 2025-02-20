import azure.functions as func

bp = func.Blueprint()

@bp.function_name('test_blueprint')
@bp.route(route='test_blueprint')
def blueprint_function(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("Blueprintで定義された関数だよ")