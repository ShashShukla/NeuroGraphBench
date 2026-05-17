"""Stateful circuit builder: a collection of neurons with cached innervations.

To be lifted from FlyBrainAtlas/visualize.py::Circuit. Surface preserved:

    c = Circuit(client)
    c.add_neuron("LPLC2_R_1")
    c.connectivity(region={"neuropil": "PVLP"})
    c.arborization(region=...)
    c.innervation(region=...)
    c.partner_neurons(region=...)
    c.disconnected_neurons(region=...)
    c.view_canvas()

Internally delegates retrieval to `fba.client.Client` and visualization to
`ngb.canvas.Canvas`.

Bug to fix on lift: `partner_neurons` in the original code references a free
variable `driver` instead of `self.driver` — would NameError. Lifted version
must use `self.client`.
"""
