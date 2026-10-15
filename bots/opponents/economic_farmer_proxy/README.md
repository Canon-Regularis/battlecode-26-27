# Economic Farmer Proxy

Local benchmark archetype, not a reproduction of any team's private bot. It starts from the validated G2 gameplay policy and changes the draft priority to Tavi / Cassi & Issac / Varg / Vesper / Ryth. On maps with four or five picks, this composition has an extra acting body from the paired draft selection and Vesper's gold passive; on three-pick maps it tests the Tavi / pair / Varg opening.

The proxy is not considered a strong benchmark until it demonstrates that in local matches. It currently uses the canonical nearest-camp and immediate-bank policy, so it is a composition/economy archetype rather than an independent route optimizer.

Build from the repository root:

```powershell
cambc build bots/opponents/economic_farmer_proxy
```

Store only proxy matches under `results/` and their replay bundles under `replays/economic_farmer_proxy/`.
