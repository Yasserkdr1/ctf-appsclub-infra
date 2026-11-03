package main

import (
	"github.com/ctfer-io/chall-manager/sdk"
	k8s "github.com/ctfer-io/chall-manager/sdk/kubernetes"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi"
)

const (
	baseFlag = "CTF{vibechain_supply_cache_confusion}"

	// Adresse privée du worker K3s
	workerIP = "10.60.2.10"

	// Image à publier dans un registre avant déploiement
	challengeImage = "ghcr.io/yasserkdr1/ctf-vibechain:v0.1.0"
)

func main() {
	sdk.Run(func(
		req *sdk.Request,
		resp *sdk.Response,
		opts ...pulumi.ResourceOption,
	) error {

		// Flag propre à l'identité de l'instance
		flag := pulumi.String(sdk.Variate(
			req.Config.Identity,
			baseFlag,
			sdk.WithSpecial(true),
		))

		challenge, err := k8s.NewExposedMonopod(
			req.Ctx,
			"vibechain",
			&k8s.ExposedMonopodArgs{
				Identity: pulumi.String(req.Config.Identity),
				Hostname: pulumi.String(workerIP),

				// Premier pilote : accès depuis la gateway
				FromCIDR: pulumi.String("10.60.1.10/32"),

				Container: k8s.ContainerArgs{
					Image: pulumi.String(challengeImage),

					Ports: k8s.PortBindingArray{
						k8s.PortBindingArgs{
							Port:       pulumi.Int(8000),
							ExposeType: k8s.ExposeNodePort,
						},
					},

					Envs: k8s.PrinterMap{
						"FLAG": k8s.ToPrinter(flag),
					},

					LimitCPU:    pulumi.StringPtr("500m"),
					LimitMemory: pulumi.StringPtr("256Mi"),
				},
			},
			opts...,
		)
		if err != nil {
			return err
		}

		resp.ConnectionInfo = pulumi.Sprintf(
			"http://%s",
			challenge.URLs.MapIndex(pulumi.String("8000/TCP")),
		)

		resp.Flag = flag.ToStringOutput()

		return nil
	})
}
