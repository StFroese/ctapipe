import astropy.units as u
import numpy as np
from scipy.stats import multivariate_normal
from scipy.spatial.transform import Rotation as R


__all__ = [
    "Gaussian",
]


class Gaussian:
    @u.quantity_input(
        x=u.m, y=u.m, phi=u.deg, theta=u.deg, h_bary=u.m, width=u.m, length=u.m
    )
    def __init__(self, Nc, x, y, phi, theta, h_bary, width, length):
        """Create a 3D gaussian shower model for imaging.

        Parameters
        ----------
        Nc : int
            Number of cherenkov photons in shower
        x : u.Quantity[length]
            x coord of shower intersection on ground
        y : u.Quantity[length]
            y coord of shower intersection on ground
        phi : u.Quantity[angle]
            azimuthal angle defining orientation of shower
        theta : u.Quantity[angle]
            polar angle defining orientation of shower
        h_bary : u.Quantity[length]
            height of the barycenter of the shower above ground
        width : u.Quantity[length]
            width of the shower
        length : u.Quantity[length]
            length of the shower
        """
        self.Nc = Nc
        self.x = x
        self.y = y
        self.phi = phi
        self.theta = theta
        self.h_bary = h_bary
        self.width = width
        self.length = length

    def density(self, x, y, z):
        """Returns 3D gaussian with barycenter as the mean and width and height in the covariance matrix.
        This matrix is rotated with the azimuthal and polar angle.
        """
        mean = self.barycenter()

        # Rotate covariance matrix
        cov = np.zeros((3, 3)) * u.m
        cov[0, 0] = self.width
        cov[1, 1] = self.width
        cov[2, 2] = self.length

        r = R.from_rotvec([0, self.theta.to_value(u.rad), self.phi.to_value(u.rad)])
        cov = r.as_matrix().T @ cov @ r.as_matrix()

        gauss = multivariate_normal(mean=mean.to_value(u.m), cov=cov.to_value(u.m))

        return self.Nc * gauss.pdf(np.array([x, y, z]))

    def barycenter(self):
        """Calculates barycenter of the shower.
        This is given by the vector defined by phi and theta in spherical coords + vector pointing to the intersection.
        """
        b = np.zeros(3) * u.m
        b[0] = (
            self.h_bary
            * np.cos(self.phi.to_value(u.rad))
            * np.tan(self.theta.to_value(u.rad))
            + self.x
        )
        b[1] = (
            self.h_bary
            * np.sin(self.phi.to_value(u.rad))
            * np.tan(self.theta.to_value(u.rad))
            + self.y
        )
        b[2] = self.h_bary
        return b