package main

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"

	"github.com/ctfer-io/chall-manager/sdk"
	k8s "github.com/ctfer-io/chall-manager/sdk/kubernetes"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi"
)

const (
	baseFlag       = "bwctf{uN10n_&nd_cr4ck}"
	workerIP       = "10.60.2.10"
	challengeImage = "ghcr.io/yasserkdr1/ctf-stream:v0.1.0"
)

func main() {
	sdk.Run(func(req *sdk.Request, resp *sdk.Response, opts ...pulumi.ResourceOption) error {
		// Same deterministic per-identity variation pattern as AppsClub Loopback:
		// keep the original author message, only append a hex suffix.
		varied := sdk.Variate(req.Config.Identity, baseFlag, sdk.WithSpecial(true))
		digest := sha256.Sum256([]byte(varied))
		flag := pulumi.String(strings.TrimSuffix(baseFlag, "}") + "_" + hex.EncodeToString(digest[:8]) + "}")

		if err := req.Ctx.RegisterStackTransformation(hardenDeployment); err != nil {
			return err
		}

		challenge, err := k8s.NewExposedMonopod(
			req.Ctx,
			"stream",
			&k8s.ExposedMonopodArgs{
				Identity: pulumi.String(req.Config.Identity),
				Hostname: pulumi.String(workerIP),
				FromCIDR: pulumi.String("10.60.1.10/32"),
				Container: k8s.ContainerArgs{
					Image: pulumi.String(challengeImage),
					Ports: k8s.PortBindingArray{
						k8s.PortBindingArgs{
							Port:       pulumi.Int(8080),
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

		// The AppsClub VIP controller translates this dynamic NodePort to a private VIP.
		resp.ConnectionInfo = pulumi.Sprintf("http://%s", challenge.URLs.MapIndex(pulumi.String("8080/TCP")))
		resp.Flag = flag.ToStringOutput()
		return nil
	})
}
