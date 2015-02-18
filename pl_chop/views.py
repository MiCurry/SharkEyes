from django.shortcuts import render
from django.http import HttpResponse
from pl_plot.models import Overlay
from pl_chop.tasks import tile_overlay
from pl_chop.models import TileManager
from django.http import Http404


def test_chop(request):
    #Validate User Permissions
    if request.user.is_anonymous():
        raise Http404("You do not have admin permissions to this site. Please contact your page administrator.")
    else:
        results = TileManager.get_task_to_tile_next_few_days_of_untiled_overlays()
        if results is None:
            return HttpResponse("Nothing to tile")
        else:
            # todo this blocks until it finishes tiling. Once celerycam works, have it just return since then we can check in the admin
            return HttpResponse(results.get().__str__())