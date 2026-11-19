package main

import (
	"crypto/sha256"
	"encoding/hex"
	"github.com/ctfer-io/chall-manager/sdk"
	k8s "github.com/ctfer-io/chall-manager/sdk/kubernetes"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi"
	"strings"
)

const (
	baseFlag = "bwctf{h34d3rs_4r3_n0t_4uth3nt1c4t10n_D2R1F}"

	// Adresse privée du worker K3s
	workerIP = "10.60.2.10"

	// Image à publier dans un registre avant déploiement
	challengeImage = "ghcr.io/yasserkdr1/ctf-loopback:v0.1.0"
)

func main() {
	sdk.Run(func(
		req *sdk.Request,
		resp *sdk.Response,
		opts ...pulumi.ResourceOption,
	) error {

		// Flag propre à l'identité de l'instance
		varied := sdk.Variate(req.Config.Identity, baseFlag, sdk.WithSpecial(true))
		nonce := sha256.Sum256([]byte(varied))
		flag := pulumi.String(
			strings.TrimSuffix(baseFlag, "}") + "_" +
				hex.EncodeToString(nonce[:8]) + "}",
		)

		if err := req.Ctx.RegisterStackTransformation(hardenDeployment); err != nil {
			return err
		}

		challenge, err := k8s.NewExposedMonopod(
			req.Ctx,
			"loopback",
			&k8s.ExposedMonopodArgs{
				Identity: pulumi.String(req.Config.Identity),
				Hostname: pulumi.String(workerIP),

				// Premier pilote : accès depuis la gateway
				FromCIDR: pulumi.String("10.60.1.10/32"),

				Container: k8s.ContainerArgs{
					Image: pulumi.String(challengeImage),

					Ports: k8s.PortBindingArray{
						k8s.PortBindingArgs{
							Port:       pulumi.Int(5000),
							ExposeType: k8s.ExposeNodePort,
						},
					},

					Envs: k8s.PrinterMap{
						"FLAG": k8s.ToPrinter(flag),
					},

					Requests: pulumi.StringMap{
						"cpu":    pulumi.String("50m"),
						"memory": pulumi.String("64Mi"),
					},
					Limits: pulumi.StringMap{
						"cpu":    pulumi.String("500m"),
						"memory": pulumi.String("256Mi"),
					},
				},
			},
			opts...,
		)
		if err != nil {
			return err
		}

		resp.ConnectionInfo = pulumi.Sprintf(
			"http://%s",
			challenge.URLs.MapIndex(pulumi.String("5000/TCP")),
		)

		resp.Flag = flag.ToStringOutput()

		return nil
	})
}
