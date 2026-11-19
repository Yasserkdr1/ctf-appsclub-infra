package main

import (
	"github.com/ctfer-io/chall-manager/sdk"
	k8s "github.com/ctfer-io/chall-manager/sdk/kubernetes"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi"
)

const (
	// Keep the original challenge flag as the seed; Chall-Manager varies
	// the flag per instance identity. Do not put this in the Docker image.
	baseFlag = "bwctf{y0u_h1t_th3_jackp0t_D5R1F}"

	workerIP = "10.60.2.10"
	// The image must be published before a remote instance can start.
	challengeImage = "ghcr.io/yasserkdr1/ctf-hit-ghost-jackpot:v0.1.0"
)

func main() {
	sdk.Run(func(
		req *sdk.Request,
		resp *sdk.Response,
		opts ...pulumi.ResourceOption,
	) error {
		flag := pulumi.String(sdk.Variate(
			req.Config.Identity,
			baseFlag,
			sdk.WithSpecial(true),
		))

		// Preserve the hardened Deployment transformation already used by VibeChain.
		if err := req.Ctx.RegisterStackTransformation(hardenDeployment); err != nil {
			return err
		}

		challenge, err := k8s.NewExposedMonopod(
			req.Ctx,
			"ghost-jackpot",
			&k8s.ExposedMonopodArgs{
				Identity: pulumi.String(req.Config.Identity),
				Hostname: pulumi.String(workerIP),

				// NodePort is reachable by the gateway, not directly by players.
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

		// The private backend URL is translated by AppsClub's CTFd integration
		// to the correct team VIP. Never display the raw NodePort to players.
		resp.ConnectionInfo = pulumi.Sprintf(
			"http://%s",
			challenge.URLs.MapIndex(pulumi.String("5000/TCP")),
		)
		resp.Flag = flag.ToStringOutput()
		return nil
	})
}
