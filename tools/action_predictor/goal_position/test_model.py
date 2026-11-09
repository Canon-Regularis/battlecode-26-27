import copy,unittest
import numpy as np
import torch
from . import model


class GoalModelTests(unittest.TestCase):
    def fixture(self):
        own=dict(entity=dict(kind=1,index=0),known=15,team=0,type=1,position=dict(x=1,y=1),health=100,items=[0,1])
        enemy=dict(entity=dict(kind=1,index=4),known=0,team=1,type=2,position=dict(x=4,y=4),health=9999)
        camp=dict(entity=dict(kind=2,index=9),known=15,position=dict(x=4,y=2),health=50)
        row=dict(event='99:0',observation=dict(own=own,entities=[enemy,camp]),
            supplement=dict(pre='98:0',own=dict(gold=10),movement=[dict(x=2,y=1)],restrictions=0))
        route=dict(width=6,height=5,blocked=[0],spawns=[dict(minX=0,maxX=1,minY=1,maxY=2),dict(minX=5,maxX=6,minY=4,maxY=5)],altars=[dict(x=4,y=3)],submit_range=1)
        return row,route

    def test_hidden_dynamics_ids_and_future_labels_cannot_enter(self):
        row,route=self.fixture();keys=model.schema([row]);a=model.encode(row,route,keys)
        row['goal']=[4,4];row['event']='9999:0';row['observation']['own']['entity']['index']=8
        row['observation']['entities'][0].update(health=-123,position=dict(x=0,y=0))
        b=model.encode(row,route,keys)
        for k in ('grid','own','entities','positions'):self.assertTrue(torch.equal(a[k],b[k]))

    def test_all_map_tiles_and_known_entities_encoded(self):
        row,route=self.fixture();keys=model.schema([row]);a=model.encode(row,route,keys)
        self.assertEqual(a['grid'].shape,(11,5,6));self.assertEqual(len(a['entities']),3)
        self.assertEqual(a['positions'][1].tolist(),[-1,-1])
        self.assertFalse(a['valid'][0,0]);self.assertEqual(a['unencoded_fields'],0)
        self.assertIn('/self/items/1',keys['own'])

    def test_gradients_and_normalization(self):
        row,route=self.fixture();keys=model.schema([row]);torch.manual_seed(1);net=model.GoalMap(keys)
        a=model.batch([model.encode(row,route,keys)]);logits=net(**a)
        self.assertTrue(torch.isneginf(logits[0,0,0]));self.assertAlmostEqual(logits.flatten(1).softmax(1).sum().item(),1,places=6)
        torch.nn.functional.cross_entropy(logits.flatten(1),torch.tensor([16])).backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in net.parameters()))
        self.assertGreater(net.entity[0].weight.grad.abs().sum().item(),0)

    def test_padding_and_entity_order(self):
        row,route=self.fixture();keys=model.schema([row]);torch.manual_seed(1);net=model.GoalMap(keys).eval()
        a=model.encode(row,route,keys);other=copy.deepcopy(row);other['observation']['entities'].reverse()
        b=model.encode(other,route,keys)
        with torch.no_grad():x=net(**model.batch([a]));y=net(**model.batch([b]))
        torch.testing.assert_close(x,y)
        bigger=copy.deepcopy(route);bigger['width']=7;bigger['height']=7
        c=model.encode(row,bigger,keys)
        with torch.no_grad():z=net(**model.batch([a,c]))
        torch.testing.assert_close(x,z[:1,:5,:6],atol=1e-6,rtol=1e-5)
        self.assertTrue(torch.isneginf(z[0,5:,:]).all())

    def test_adapter_respects_command_and_unavailable_path(self):
        row,route=self.fixture()
        self.assertEqual(model.adapt_movement('attack',(4,2),route,row,(4,3)),(4,2))
        self.assertEqual(model.adapt_movement('move',(2,1),route,row,(0,0)),(2,1))
        self.assertEqual(model.adapt_movement('move',(1,2),route,row,(4,3)),(2,1))


if __name__=='__main__':unittest.main()
