"""
Adapted from:
http://pytorch.org/vision/main/_modules/torchvision/datasets/lsun.html#LSUN
"""
import string
import os
import pickle
import lmdb
import io
from PIL import Image

from torch.utils.data import DataLoader
import torch
from torchvision.datasets.utils import verify_str_arg, iterable_to_str
from torchvision.datasets.vision import VisionDataset
from torchvision import transforms
from typing import Union, Optional, Callable, List, cast, Any, Tuple
from collections.abc import Iterable


class LSUNClass(VisionDataset):
    def __init__(
        self, root: str, transform: Optional[Callable] = None, target_transform: Optional[Callable] = None
    ) -> None:
        super().__init__(root, transform=transform, target_transform=target_transform)

        self.env = lmdb.open(root, max_readers=1, readonly=True, lock=False, readahead=False, meminit=False)
        with self.env.begin(write=False) as txn:
            self.length = txn.stat()["entries"]
        cache_file = "_cache_" + "".join(c for c in root if c in string.ascii_letters)
        if os.path.isfile(cache_file):
            self.keys = pickle.load(open(cache_file, "rb"))
        else:
            with self.env.begin(write=False) as txn:
                self.keys = [key for key in txn.cursor().iternext(keys=True, values=False)]
            pickle.dump(self.keys, open(cache_file, "wb"))

    def __getitem__(self, index: int) -> Tuple[Any, Any]:
        img, target = None, None
        env = self.env
        with env.begin(write=False) as txn:
            imgbuf = txn.get(self.keys[index])

        buf = io.BytesIO()
        buf.write(imgbuf)
        buf.seek(0)
        img = Image.open(buf).convert("RGB")

        if self.transform is not None:
            img = self.transform(img)

        if self.target_transform is not None:
            target = self.target_transform(target)

        return img, target

    def __len__(self) -> int:
        return self.length


class LSUNCustomDataLoader(VisionDataset):
    """`LSUN <https://www.yf.io/p/lsun>`_ dataset.

    You will need to install the ``lmdb`` package to use this dataset: run
    ``pip install lmdb``

    Args:
        root (string): Root directory for the database files.
        classes (string or list): One of {'train', 'val', 'test'} or a list of
            categories to load. e,g. ['bedroom_train', 'church_outdoor_train'].
        transform (callable, optional): A function/transform that  takes in an PIL image
            and returns a transformed version. E.g, ``transforms.RandomCrop``
        target_transform (callable, optional): A function/transform that takes in the
            target and transforms it.
    """

    def __init__(
        self,
        root: str,
        classes: Union[str, List[str]] = "train",
        transform: Optional[Callable] = None,
        target_transform: Optional[Callable] = None,
    ) -> None:
        super().__init__(root, transform=transform, target_transform=target_transform)
        self.classes = self._verify_classes(classes)

        # for each class, create an LSUNClassDataset
        self.dbs = []
        for c in self.classes:
            self.dbs.append(LSUNClass(root=root, transform=transform))

        self.indices = []
        count = 0
        for db in self.dbs:
            count += len(db)
            self.indices.append(count)

        self.length = count

    def _verify_classes(self, classes: Union[str, List[str]]) -> List[str]:
        categories = [
            "sheep",
            "bedroom",
            "bridge",
            "church_outdoor",
            "classroom",
            "conference_room",
            "dining_room",
            "kitchen",
            "living_room",
            "restaurant",
            "tower",
        ]
        dset_opts = ["train", "val", "test"]

        try:
            classes = cast(str, classes)
            verify_str_arg(classes, "classes", dset_opts)
            if classes == "test":
                classes = [classes]
            else:
                classes = [c + "_" + classes for c in categories]
        except ValueError:
            if not isinstance(classes, Iterable):
                msg = "Expected type str or Iterable for argument classes, but got type {}."
                raise ValueError(msg.format(type(classes)))

            classes = list(classes)
            msg_fmtstr_type = "Expected type str for elements in argument classes, but got type {}."
            for c in classes:
                verify_str_arg(c, custom_msg=msg_fmtstr_type.format(type(c)))
                c_short = c.split("_")
                category, dset_opt = "_".join(c_short[:-1]), c_short[-1]

                msg_fmtstr = "Unknown value '{}' for {}. Valid values are {{{}}}."
                msg = msg_fmtstr.format(category, "LSUN class", iterable_to_str(categories))
                verify_str_arg(category, valid_values=categories, custom_msg=msg)

                msg = msg_fmtstr.format(dset_opt, "postfix", iterable_to_str(dset_opts))
                verify_str_arg(dset_opt, valid_values=dset_opts, custom_msg=msg)

        return classes

    def __getitem__(self, index: int) -> Tuple[Any, Any]:
        """
        Args:
            index (int): Index

        Returns:
            tuple: Tuple (image, target) where target is the index of the target category.
        """
        target = 0
        sub = 0
        for ind in self.indices:
            if index < ind:
                break
            target += 1
            sub = ind

        db = self.dbs[target]
        index = index - sub

        if self.target_transform is not None:
            target = self.target_transform(target)

        img, _ = db[index]
        return img, target

    def __len__(self) -> int:
        return self.length

    def extra_repr(self) -> str:
        return "Classes: {classes}".format(**self.__dict__)


def get_lsun_dataloader(path_to_data='./data', dataset="sheep_train",
                        batch_size=64):
    """LSUN dataloader with (128, 128) sized images.
    path_to_data : str
        One of 'bedroom_val' or 'bedroom_train'
    """
    # Compose transforms
    transform = transforms.Compose([
        transforms.Resize(64),
        transforms.CenterCrop(64),
        transforms.ToTensor()
    ])

    # Get dataset
    lsun_dset = LSUNCustomDataLoader(root=path_to_data, classes=[dataset], transform=transform)
    print(len(lsun_dset))
    sub_lsun_dset = torch.utils.data.Subset(lsun_dset, [i for i in range(200000)])
    print(len(sub_lsun_dset))
    # subset for test
    sub_lsun_test = torch.utils.data.Subset(lsun_dset, [i for i in range(128)])
    # Create dataloader
    return DataLoader(sub_lsun_dset, batch_size=batch_size, shuffle=True), DataLoader(sub_lsun_test, batch_size=batch_size, shuffle=True)


if __name__ == "__main__":
    # Todo: change path to local path to .mdb file
    train_loader, test_loader = get_lsun_dataloader('/media/anna/54F8F2E0F8F2BF74/CSC413Project/data/sheep')
